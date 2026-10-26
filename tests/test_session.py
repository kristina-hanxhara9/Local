import pytest

from meeting_companion.config.settings import Settings
from meeting_companion.services.meeting_session import MeetingSession
from meeting_companion.services.transcript_storage import TranscriptStorage
from tests.fakes import FakeClient, FakePipeline, until


@pytest.fixture
def session(tmp_path):
    client = FakeClient()
    service = MeetingSession(Settings(autosave=True), TranscriptStorage(tmp_path), client, FakePipeline)
    yield service
    if not service.closed.is_set():
        service.command("shutdown")
        until(service.closed.is_set)


def test_no_capture_at_creation_and_duplicate_start_is_rejected(session):
    assert session.state == "idle"
    assert session.client.sessions == []
    assert session.start("Meeting")
    assert not session.start("Duplicate")
    until(lambda: session.state == "recording")
    assert len(session.client.sessions) == 1


def test_pause_releases_devices_and_resume_creates_fresh_stream(session):
    session.start()
    until(lambda: session.state == "recording")
    first_capture = session.capture
    first_sdk = session.client.sessions[0]
    session.command("pause")
    until(lambda: session.state == "paused")
    assert first_capture.stopped and first_sdk.stopped
    session.command("resume")
    until(lambda: session.state == "recording")
    assert len(session.client.sessions) == 2
    assert session.capture is not first_capture
    session.command("stop")
    until(lambda: session.state == "stopped")
    assert len(session.snapshot().entries) == 2  # Each session's flushed final is preserved.


def test_stop_flushes_real_sdk_results_before_final_transaction(session):
    session.start("Planning")
    until(lambda: session.state == "recording")
    session.client.sessions[0].emit()
    until(lambda: len(session.snapshot().entries) == 1)
    session.update_metadata("Revised title", "Notes entered during meeting")
    session.command("stop")
    until(lambda: session.state == "stopped")
    until(lambda: bool(session.storage.search("Tail fixture")))
    saved = session.storage.load(session.snapshot().id)
    assert saved.title == "Revised title" and saved.notes == "Notes entered during meeting"
    assert saved.status == "completed"
    assert len(saved.entries) == 2
    assert session.client.sessions[0].stopped


def test_device_loss_interrupts_and_saves_instead_of_fabricating_speech(session):
    session.start()
    until(lambda: session.state == "recording")
    session.capture.error = "Loopback device disconnected"
    until(lambda: session.state == "error")
    assert session.snapshot().status == "interrupted"
    errors = list(session.events.queue)
    assert any(kind == "error" and "Loopback" in value for kind, value in errors)
    assert all("Loopback" not in e.text for e in session.snapshot().entries)


def test_sdk_failure_is_contained_and_audio_stops(session):
    session.start()
    until(lambda: session.state == "recording")
    capture = session.capture
    session.client.sessions[0].results.put(RuntimeError("Native model failed"))
    until(lambda: session.state == "error")
    assert capture.stopped
    assert session.snapshot().status == "interrupted"


def test_first_run_without_autosave_does_not_write_meeting(tmp_path):
    service = MeetingSession(Settings(autosave=False), TranscriptStorage(tmp_path), FakeClient(), FakePipeline)
    service.start()
    until(lambda: service.state == "recording")
    service.command("stop")
    until(lambda: service.state == "stopped")
    assert service.storage.search() == []
    service.command("shutdown")
    until(service.closed.is_set)


def test_explicit_save_during_capture_is_finalized_on_stop(tmp_path):
    service = MeetingSession(Settings(autosave=False), TranscriptStorage(tmp_path), FakeClient(), FakePipeline)
    service.start()
    until(lambda: service.state == "recording")
    service.command("save")
    until(lambda: service.persist_on_finish)
    service.command("stop")
    until(lambda: service.state == "stopped")
    until(lambda: bool(service.storage.search("Tail fixture")))
    assert service.storage.load(service.snapshot().id).status == "completed"
    service.command("shutdown")
    until(service.closed.is_set)


def test_shutdown_releases_capture_then_unloads_model(session):
    session.start()
    until(lambda: session.state == "recording")
    capture = session.capture
    session.command("shutdown")
    until(session.closed.is_set)
    assert capture.stopped and session.client.sessions[0].stopped and session.client.unloaded


def test_failed_previous_meeting_save_does_not_discard_it(session, monkeypatch):
    session.start("Keep this")
    until(lambda: session.state == "recording")
    session.command("stop")
    until(lambda: session.state == "stopped")
    previous = session.snapshot().id

    def fail(_):
        raise OSError("Disk full")

    monkeypatch.setattr(session.storage, "save", fail)
    assert session.start("New meeting", save_previous=True)
    until(lambda: session.state == "error")
    assert session.snapshot().id == previous
    assert len(session.client.sessions) == 1


def test_save_failure_keeps_capture_running_and_quit_preserves_transcript(session, monkeypatch):
    session.start("Keep this meeting")
    until(lambda: session.state == "recording")
    original_save = session.storage.save

    def fail(_):
        raise OSError("Disk full")

    monkeypatch.setattr(session.storage, "save", fail)
    session.command("save")
    until(lambda: session.last_save_error is not None)
    assert session.state == "recording"
    session.command("shutdown", True)
    until(lambda: any(kind == "quit_cancelled" for kind, _ in list(session.events.queue)))
    assert not session.closed.is_set()
    assert session.snapshot().title == "Keep this meeting"
    assert session.snapshot().entries[-1].text == "Tail fixture"
    monkeypatch.setattr(session.storage, "save", original_save)
    session.command("shutdown", True)
    until(session.closed.is_set)
    assert session.storage.load(session.snapshot().id).status == "completed"


def test_enabling_autosave_during_meeting_applies_to_current_session(tmp_path):
    service = MeetingSession(Settings(autosave=False), TranscriptStorage(tmp_path), FakeClient(), FakePipeline)
    service.start()
    until(lambda: service.state == "recording")
    service.command("preferences", Settings(autosave=True))
    until(lambda: service.capture_settings.autosave)
    service.command("stop")
    until(lambda: service.state == "stopped")
    until(lambda: bool(service.storage.search("Tail fixture")))
    service.command("shutdown")
    until(service.closed.is_set)
