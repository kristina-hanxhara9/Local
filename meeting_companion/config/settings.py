from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

MODES = ("Both", "Microphone only", "Computer audio only")
MODEL_ALIAS = "nemotron-speech-streaming-en-0.6b"


def data_directory() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return base / "MeetingCompanion"


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@dataclass
class Settings:
    storage_dir: str = ""
    mode: str = "Both"
    microphone: str = ""  # Persistent name + host API, never a stale device index.
    loopback: str = ""
    theme: str = "light"
    always_on_top: bool = True
    autosave: bool = False
    reminders: bool = False
    reminder_minutes: int = 30
    cooldown_minutes: int = 60
    startup: bool = False
    setup_complete: bool = False
    providers_provisioned: bool = False
    echo_reduction: bool = True

    @property
    def directory(self) -> Path:
        return Path(self.storage_dir).expanduser() if self.storage_dir else data_directory() / "Transcripts"

    def validate(self) -> None:
        if self.mode not in MODES or self.theme not in ("light", "dark"):
            raise ValueError("Choose a valid audio mode and theme.")
        if not 5 <= self.reminder_minutes <= 1440 or not 5 <= self.cooldown_minutes <= 1440:
            raise ValueError("Reminder intervals and cooldown must be between 5 and 1440 minutes.")
        for name in ("always_on_top", "autosave", "reminders", "startup", "setup_complete",
                     "providers_provisioned", "echo_reduction"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"Invalid boolean setting: {name}")

    def save(self, path: Path | None = None) -> None:
        self.validate()
        atomic_text(path or data_directory() / "settings.json", json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        path = path or data_directory() / "settings.json"
        if not path.exists():
            return cls()
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Settings file must contain a JSON object.")
        result = cls(**{k: v for k, v in value.items() if k in cls.__dataclass_fields__})
        result.validate()
        return result
