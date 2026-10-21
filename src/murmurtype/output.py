# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import subprocess
import time

from murmurtype.config import Config, PasteKeys

log = logging.getLogger(__name__)

# Linux input event codes (linux/input-event-codes.h): 29 = left Ctrl, 42 = left Shift, 47 = V.
# ydotool sends raw key codes, so this works regardless of the keyboard layout.
KEY_SEQUENCES = {
    PasteKeys.CTRL_V: ["29:1", "47:1", "47:0", "29:0"],
    PasteKeys.CTRL_SHIFT_V: ["29:1", "42:1", "47:1", "47:0", "42:0", "29:0"],
}

CLIPBOARD_RESTORE_DELAY_SECONDS = 0.5


def read_clipboard_text() -> str | None:
    result = subprocess.run(
        ["wl-paste", "--no-newline", "--type", "text"],
        capture_output=True,
        timeout=2,
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace")


def write_clipboard(text: str):
    subprocess.run(["wl-copy"], input=text.encode("utf-8"), check=True, timeout=5)


def deliver(text: str, config: Config):
    """Put text into the clipboard and paste it into the focused window.

    Text goes through the clipboard instead of `ydotool type`, because ydotool types
    with US-layout key codes and garbles non-ASCII characters such as Polish diacritics.
    """
    if config.trailing_space:
        text += " "
    previous = read_clipboard_text() if config.restore_clipboard else None

    write_clipboard(text)
    if config.paste_keys == PasteKeys.NONE:
        return

    # Give wl-copy a moment to take ownership of the clipboard, otherwise the
    # target app may paste the previous content.
    time.sleep(config.paste_delay_seconds)
    subprocess.run(["ydotool", "key", *KEY_SEQUENCES[config.paste_keys]], check=True, timeout=5)

    if previous is not None:
        time.sleep(CLIPBOARD_RESTORE_DELAY_SECONDS)
        write_clipboard(previous)
