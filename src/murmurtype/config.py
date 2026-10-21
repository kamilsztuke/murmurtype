import os
import tomllib
from dataclasses import dataclass, fields
from enum import StrEnum
from pathlib import Path

CONFIG_PATH = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    / "murmurtype"
    / "config.toml"
)


class Device(StrEnum):
    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"


class PasteKeys(StrEnum):
    CTRL_V = "ctrl+v"
    CTRL_SHIFT_V = "ctrl+shift+v"
    NONE = "none"


@dataclass(frozen=True)
class Config:
    model: str = "large-v3-turbo"
    language: str = "pl"
    initial_prompt: str = ""
    beam_size: int = 5

    device: Device = Device.AUTO
    cpu_compute_type: str = "int8"
    cpu_threads: int = 0
    cuda_compute_type: str = "float16"
    cuda_min_free_mb: int = 3000
    cuda_idle_unload_seconds: float = 300

    silence_threshold_db: float = -40.0
    silence_seconds: float = 2.0
    no_speech_timeout_seconds: float = 8.0
    max_seconds: float = 120.0

    paste_keys: PasteKeys = PasteKeys.CTRL_V
    paste_delay_seconds: float = 0.15
    trailing_space: bool = True
    restore_clipboard: bool = False
    notifications: bool = True

    def __post_init__(self):
        # Coerce TOML strings into enums so invalid values fail at startup, not mid-dictation.
        object.__setattr__(self, "device", Device(self.device))
        object.__setattr__(self, "paste_keys", PasteKeys(self.paste_keys))
        if self.silence_seconds < 0:
            raise ValueError(f"silence_seconds must be >= 0 (0 disables), got {self.silence_seconds}")


def load_config(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()
    with path.open("rb") as file:
        data = tomllib.load(file)
    known_keys = {field.name for field in fields(Config)}
    unknown_keys = set(data) - known_keys
    if unknown_keys:
        raise ValueError(
            f"Unknown keys in {path}: {', '.join(sorted(unknown_keys))}"
        )
    return Config(**data)
