from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from meeting_companion.config.settings import atomic_text
from .models import Entry, Meeting


class TranscriptStorage:
    """Short, atomic transactions; each caller owns its own connection."""

    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "meetings.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS meetings (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, started TEXT NOT NULL,
                    duration REAL NOT NULL, mode TEXT NOT NULL, notes TEXT NOT NULL,
                    status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS entries (
                    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
                    seq INTEGER NOT NULL, offset REAL NOT NULL, text TEXT NOT NULL,
                    end REAL, PRIMARY KEY(meeting_id, seq));
                CREATE INDEX IF NOT EXISTS meeting_date ON meetings(started DESC);
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def save(self, meeting: Meeting) -> None:
        with self.connect() as db:
            db.execute("""INSERT INTO meetings VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title, duration=excluded.duration,
                notes=excluded.notes, status=excluded.status""",
                       (meeting.id, meeting.title, meeting.started, meeting.duration,
                        meeting.mode, meeting.notes, meeting.status))
            last = db.execute("SELECT COALESCE(MAX(seq), -1) FROM entries WHERE meeting_id=?", (meeting.id,)).fetchone()[0]
            db.executemany("INSERT INTO entries VALUES (?, ?, ?, ?, ?) ON CONFLICT(meeting_id, seq) DO NOTHING",
                           ((meeting.id, i, e.offset, e.text, e.end)
                            for i, e in enumerate(meeting.entries[last + 1:], start=last + 1)))

    def search(self, query: str = "", limit: int = 200) -> list[tuple]:
        # Escape LIKE metacharacters so user input is a literal substring.
        pattern = "%" + query.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
        with self.connect() as db:
            return db.execute("""SELECT id, title, started, duration, status FROM meetings m
                WHERE title LIKE ? ESCAPE '!' OR notes LIKE ? ESCAPE '!'
                OR EXISTS (SELECT 1 FROM entries e WHERE e.meeting_id=m.id
                           AND e.text LIKE ? ESCAPE '!')
                ORDER BY started DESC LIMIT ?""", (pattern, pattern, pattern, limit)).fetchall()

    def load(self, meeting_id: str) -> Meeting:
        with self.connect() as db:
            row = db.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
            if row is None:
                raise KeyError("This meeting no longer exists.")
            entries = [Entry(*r) for r in db.execute(
                "SELECT offset, text, end FROM entries WHERE meeting_id=? ORDER BY seq", (meeting_id,))]
        return Meeting(id=row[0], title=row[1], started=row[2], duration=row[3], mode=row[4],
                       notes=row[5], status=row[6], entries=entries)

    def delete(self, meeting_id: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM meetings WHERE id=?", (meeting_id,))

    @staticmethod
    def export(meeting: Meeting, path: Path) -> None:
        atomic_text(path, meeting.render(markdown=path.suffix.lower() == ".md"))
