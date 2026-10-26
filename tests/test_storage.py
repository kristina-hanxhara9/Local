from dataclasses import replace
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from meeting_companion.services.models import Entry, Meeting, timestamp
from meeting_companion.services.transcript_storage import TranscriptStorage


def test_progressive_save_updates_metadata_and_preserves_final_entries(tmp_path):
    store = TranscriptStorage(tmp_path)
    meeting = Meeting(title="Budget review", entries=[Entry(1, "Real speech", 3)])
    store.save(meeting)
    meeting.entries.append(Entry(5, "Next statement"))
    meeting.notes = "A private note"
    meeting.title = "Revised title"
    meeting.duration = 12
    meeting.status = "completed"
    store.save(meeting)
    store.save(meeting)
    loaded = store.load(meeting.id)
    assert loaded == meeting
    assert len(loaded.entries) == 2


@pytest.mark.parametrize("query", ["speech", "PRIVATE", "Budget", "100%", "a_b", "back\\slash", "' OR 1=1 --"])
def test_history_search_is_literal_and_covers_notes_title_and_transcript(tmp_path, query):
    store = TranscriptStorage(tmp_path)
    for meeting in (Meeting(title="Budget", notes="Private", entries=[Entry(0, "Real speech")]),
                    Meeting(entries=[Entry(0, "100% a_b back\\slash ' OR 1=1 --")])):
        store.save(meeting)
    assert len(store.search(query)) == 1


def test_delete_cascades_and_missing_id_is_clear(tmp_path):
    store = TranscriptStorage(tmp_path)
    meeting = Meeting(entries=[Entry(0, "text")])
    store.save(meeting)
    store.delete(meeting.id)
    assert store.search() == []
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 0
    with pytest.raises(KeyError):
        store.load(meeting.id)


def test_failed_transaction_rolls_back_metadata_and_entries(tmp_path):
    store = TranscriptStorage(tmp_path)
    meeting = Meeting(title="Original", entries=[Entry(0, "good")])
    store.save(meeting)
    meeting.title = "Must not commit"
    meeting.entries.append(Entry(2, None))
    # An invalid new entry must roll back metadata and the entire transaction.
    with pytest.raises(Exception):
        store.save(meeting)
    assert store.load(meeting.id).title == "Original"


def test_concurrent_local_read_and_autosave(tmp_path):
    store = TranscriptStorage(tmp_path)
    meeting = Meeting(entries=[Entry(0, "text")])
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(store.save, replace(meeting, notes=str(i))) for i in range(10)]
        futures += [pool.submit(store.search, "text") for _ in range(10)]
        for future in futures:
            future.result()
    assert len(store.load(meeting.id).entries) == 1


@pytest.mark.parametrize("extension", [".txt", ".md"])
def test_export_is_utf8_and_includes_notes_and_timestamps(tmp_path, extension):
    meeting = Meeting(title="Réunion", entries=[Entry(65, "こんにちは")], notes="Follow up", duration=120)
    path = tmp_path / ("meeting" + extension)
    TranscriptStorage.export(meeting, path)
    output = path.read_text(encoding="utf-8")
    assert "[00:01:05] こんにちは" in output
    assert "Follow up" in output
    assert output.startswith("# Réunion" if extension == ".md" else "Réunion")
    assert len(list(tmp_path.iterdir())) == 1


def test_timestamp_handles_long_meetings():
    assert timestamp(3661.2) == "01:01:01"
    assert timestamp(-10) == "00:00:00"
