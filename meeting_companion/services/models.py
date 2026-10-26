from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


def timestamp(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"


@dataclass(frozen=True)
class Entry:
    offset: float
    text: str
    end: float | None = None


@dataclass
class Meeting:
    title: str = "Untitled meeting"
    id: str = field(default_factory=lambda: str(uuid4()))
    started: str = field(default_factory=lambda: datetime.now().astimezone().isoformat())
    duration: float = 0.0
    mode: str = "Both"
    notes: str = ""
    status: str = "active"
    entries: list[Entry] = field(default_factory=list)

    def render(self, markdown: bool = False) -> str:
        heading = "# " if markdown else ""
        lines = [f"{heading}{self.title}", f"Date: {self.started}",
                 f"Duration: {timestamp(self.duration)}", f"Audio: {self.mode}",
                 f"Status: {self.status}", "", "## Transcript" if markdown else "Transcript", ""]
        lines.extend(f"[{timestamp(e.offset)}] {e.text}" for e in self.entries)
        if self.notes:
            lines.extend(["", "## Notes" if markdown else "Notes", "", self.notes])
        return "\n".join(lines) + "\n"
