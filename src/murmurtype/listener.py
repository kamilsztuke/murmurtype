# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import selectors
import time

import evdev
from evdev import ecodes

from murmurtype.client import DaemonUnavailable, request
from murmurtype.config import Config, ListenMode

log = logging.getLogger(__name__)

RECONNECT_SECONDS = 3
PROXY_SUFFIX = " (murmurtype)"
# evdev key event values; 2 is autorepeat while held and is ignored.
KEY_PRESSED = 1
KEY_RELEASED = 0


def resolve_button(name: str) -> int:
    normalized = name.strip().upper()
    code = ecodes.ecodes.get(normalized)
    if code is None or not normalized.startswith(("BTN_", "KEY_")):
        raise ValueError(
            f"Unknown button {name!r}; use a BTN_* or KEY_* name shown by `murmurtype listen --discover`"
        )
    return code


def code_name(code: int) -> str:
    name = ecodes.BTN.get(code) or ecodes.KEY.get(code) or str(code)
    # Some codes have aliases (e.g. BTN_LEFT/BTN_MOUSE); show the first one.
    return name[0] if isinstance(name, (list, tuple)) else name


def open_devices() -> list[evdev.InputDevice]:
    devices = []
    for path in evdev.list_devices():
        try:
            device = evdev.InputDevice(path)
        except PermissionError:
            log.debug("No permission for %s", path)
            continue
        if device.name.endswith(PROXY_SUFFIX):
            device.close()
            continue
        devices.append(device)
    return devices


def find_device(selector: str) -> evdev.InputDevice | None:
    """Find a device by path, exact name, or a unique case-insensitive name fragment."""
    if selector.startswith("/dev/"):
        return evdev.InputDevice(selector)
    devices = open_devices()
    exact = [device for device in devices if device.name == selector]
    partial = [device for device in devices if selector.lower() in device.name.lower()]
    chosen = None
    if exact:
        chosen = exact[0]
    elif len(partial) == 1:
        chosen = partial[0]
    elif partial:
        log.error("%r matches several devices: %s", selector, ", ".join(device.name for device in partial))
    for device in devices:
        if device is not chosen:
            device.close()
    return chosen


def command_for(mode: ListenMode, key_value: int) -> str | None:
    if mode == ListenMode.HOLD:
        return {KEY_PRESSED: "hold", KEY_RELEASED: "stop"}.get(key_value)
    return "toggle" if key_value == KEY_PRESSED else None


def send(command: str):
    try:
        response = request(command)
    except DaemonUnavailable:
        log.warning("Daemon is not running; ignoring %s", command)
        return
    if response.startswith("error"):
        log.debug("%s: %s", command, response)


def listen(config: Config):
    if not config.listen_device or not config.listen_button:
        raise SystemExit(
            "Set listen_device and listen_button in the config; "
            "find them with: murmurtype listen --discover"
        )
    button = resolve_button(config.listen_button)

    while True:
        device = find_device(config.listen_device)
        if device is None:
            log.warning("Device %r not found, retrying in %ds", config.listen_device, RECONNECT_SECONDS)
            time.sleep(RECONNECT_SECONDS)
            continue

        log.info("Listening for %s on %s (%s), mode %s%s",
                 code_name(button), device.name, device.path, config.listen_mode.value,
                 ", exclusive" if config.listen_exclusive else "")
        proxy = None
        try:
            if config.listen_exclusive:
                proxy = grab_with_proxy(device)
            for event in device.read_loop():
                is_trigger = event.type == ecodes.EV_KEY and event.code == button
                if not is_trigger:
                    if proxy:
                        proxy.write_event(event)
                    continue
                command = command_for(config.listen_mode, event.value)
                if command:
                    send(command)
        except OSError as error:
            # Unplugged, or a wireless receiver re-enumerated the device.
            log.warning("Lost %s: %s", device.name, error)
        finally:
            # Closing the device also releases the grab, so the original device
            # works again even if the proxy is gone.
            device.close()
            if proxy:
                proxy.close()
        time.sleep(RECONNECT_SECONDS)


def grab_with_proxy(device: evdev.InputDevice) -> evdev.UInput:
    """Take the device exclusively and re-emit its events through a virtual clone.

    Without this the trigger button keeps its normal function too (e.g. a mouse side
    button would also go "back" in the browser). The kernel drops the grab when the
    process exits, so a crash cannot leave the device dead.
    """
    proxy = evdev.UInput.from_device(device, name=device.name + PROXY_SUFFIX)
    device.grab()
    return proxy


def discover():
    """Print input devices, then the name of every button pressed on any of them."""
    devices = [device for device in open_devices() if ecodes.EV_KEY in device.capabilities()]
    if not devices:
        raise SystemExit("No readable input devices. Is your user in the 'input' group?")

    print("Input devices with buttons:")
    for device in devices:
        print(f"  {device.path:20} {device.name}")
    print("\nPress the button you want to use (Ctrl+C to quit). Then set in the config:")
    print('  listen_device = "<device name>"\n  listen_button = "<button>"\n')

    selector = selectors.DefaultSelector()
    for device in devices:
        selector.register(device, selectors.EVENT_READ)
    try:
        while True:
            for key, _ in selector.select():
                device = key.fileobj
                for event in device.read():
                    if event.type == ecodes.EV_KEY and event.value == KEY_PRESSED:
                        print(f'listen_device = "{device.name}"   listen_button = "{code_name(event.code)}"')
    except KeyboardInterrupt:
        pass
