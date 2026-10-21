import pytest

from dictate.config import Config, Device, PasteKeys, load_config


def test_missing_file_gives_defaults(tmp_path):
    assert load_config(tmp_path / "absent.toml") == Config()


def test_values_are_parsed_into_enums(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('device = "cpu"\npaste_keys = "ctrl+shift+v"\nsilence_seconds = 1.5\n')
    config = load_config(path)
    assert config.device is Device.CPU
    assert config.paste_keys is PasteKeys.CTRL_SHIFT_V
    assert config.silence_seconds == 1.5


def test_unknown_key_is_rejected(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('lanugage = "pl"\n')
    with pytest.raises(ValueError, match="lanugage"):
        load_config(path)


def test_invalid_enum_value_is_rejected(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('device = "gpu"\n')
    with pytest.raises(ValueError):
        load_config(path)


def test_negative_silence_seconds_is_rejected(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("silence_seconds = -1\n")
    with pytest.raises(ValueError, match="silence_seconds"):
        load_config(path)


def test_example_config_matches_defaults():
    from pathlib import Path

    example = Path(__file__).parent.parent / "config.example.toml"
    assert load_config(example) == Config()
