# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from evdev import ecodes

from murmurtype.config import ListenMode
from murmurtype.listener import KEY_PRESSED, KEY_RELEASED, code_name, command_for, resolve_button

KEY_REPEATED = 2


def test_hold_mode_records_while_pressed():
    assert command_for(ListenMode.HOLD, KEY_PRESSED) == "hold"
    assert command_for(ListenMode.HOLD, KEY_RELEASED) == "stop"
    assert command_for(ListenMode.HOLD, KEY_REPEATED) is None


def test_toggle_mode_reacts_to_press_only():
    assert command_for(ListenMode.TOGGLE, KEY_PRESSED) == "toggle"
    assert command_for(ListenMode.TOGGLE, KEY_RELEASED) is None
    assert command_for(ListenMode.TOGGLE, KEY_REPEATED) is None


def test_resolve_button_accepts_btn_and_key_names_case_insensitively():
    assert resolve_button("BTN_EXTRA") == ecodes.BTN_EXTRA
    assert resolve_button("key_f13") == ecodes.KEY_F13


@pytest.mark.parametrize("name", ["BTN_NOPE", "EV_KEY", "REL_X", ""])
def test_resolve_button_rejects_non_buttons(name):
    with pytest.raises(ValueError):
        resolve_button(name)


def test_code_name_picks_first_alias():
    assert code_name(ecodes.BTN_LEFT) == "BTN_LEFT"
    assert code_name(ecodes.KEY_F13) == "KEY_F13"
