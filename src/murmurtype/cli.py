# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import logging
import subprocess
import sys

from murmurtype.client import DaemonUnavailable, request
from murmurtype.notify import APP_NAME

COMMANDS = ["toggle", "start", "hold", "stop", "cancel", "status"]


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def send(command: str) -> int:
    try:
        response = request(command)
    except DaemonUnavailable:
        message = "Usługa murmurtype nie działa. Uruchom: systemctl --user start murmurtype"
        print(message, file=sys.stderr)
        subprocess.run(["notify-send", "--app-name", APP_NAME, "--icon", "dialog-error", APP_NAME, message])
        return 1
    print(response)
    return 1 if response.startswith("error") else 0


def run_daemon() -> int:
    from murmurtype import cuda
    from murmurtype.config import load_config

    cuda.ensure_library_path()
    configure_logging()
    # Hugging Face Hub logs every HTTP request of the model download at INFO level.
    for noisy_logger in ("httpx", "httpx2", "huggingface_hub"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Imported here, not at module level: the client runs on every shortcut press
    # and must not pay for importing faster-whisper.
    from murmurtype.daemon import serve

    serve(load_config())
    return 0


def run_listener(discover: bool) -> int:
    from murmurtype import listener
    from murmurtype.config import load_config

    configure_logging()
    if discover:
        listener.discover()
    else:
        listener.listen(load_config())
    return 0


def main():
    parser = argparse.ArgumentParser(prog="murmurtype", description="Whisper dictation for GNOME on Wayland.")
    parser.add_argument("command", choices=["daemon", "listen", *COMMANDS])
    parser.add_argument(
        "--discover", action="store_true",
        help="with listen: list input devices and print the names of pressed buttons",
    )
    arguments = parser.parse_args()
    if arguments.discover and arguments.command != "listen":
        parser.error("--discover works only with listen")
    if arguments.command == "daemon":
        sys.exit(run_daemon())
    if arguments.command == "listen":
        sys.exit(run_listener(arguments.discover))
    sys.exit(send(arguments.command))
