"""Uses the real Tk widget tree; no live devices or inference are opened."""
import tkinter as tk
import time
from dataclasses import replace

import pytest

from meeting_companion.config.settings import Settings
from meeting_companion.services.models import Entry, Meeting
from meeting_companion.ui.app import Application
from meeting_companion.ui.theme import apply_theme
from tests.fakes import until

pytestmark = pytest.mark.ui


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("meeting_companion.services.system_tray.SystemTray.start", lambda _: False)
    root = tk.Tk()
    application = Application(root, Settings(storage_dir=str(tmp_path / "history"), setup_complete=True))
    application.errors = []
    root.report_callback_exception = lambda *args: application.errors.append(args)
    yield application
    application.session.command("shutdown")
    until(application.session.closed.is_set)
    if not application.destroyed:
        for timer in root.tk.splitlist(root.tk.call("after", "info")):
            root.after_cancel(timer)
        root.destroy()


def pump(app):
    app.root.update_idletasks()
    app.root.update()


def test_native_windows_open_and_fit_content(app):
    app.show_transcript()
    app.show_history()
    # Keep Settings from attempting Windows device enumeration in a UI-only test.
    app.session.state = "paused"
    app.show_settings()
    app.session.state = "idle"
    app.show_setup()
    pump(app)
    assert app.transcript.window.winfo_exists()
    assert app.history.window.winfo_exists()
    assert app.settings_window.window.winfo_exists()
    assert app.setup_window.window.winfo_exists()
    for window in (app.root, app.transcript.window, app.settings_window.window, app.setup_window.window):
        assert window.winfo_reqheight() <= window.winfo_height(), (window.title(), window.winfo_reqheight(), window.winfo_height())
    assert not app.errors
    assert app.session.capture is None  # Opening any window must not start recording.


def test_partial_replacement_final_render_search_and_notes(app):
    app.show_transcript()
    with app.session.lock:
        app.session.meeting = Meeting(title="UI test fixture", entries=[Entry(10, "First fixture sentence.")])
        app.session.accumulator.partial = "Old hypothesis"
    app.transcript.update()
    with app.session.lock:
        app.session.accumulator.partial = "Replacement hypothesis"
    app.transcript.update()
    text = app.transcript.text.get("1.0", "end")
    assert "Old hypothesis" not in text and text.count("Replacement hypothesis") == 1
    with app.session.lock:
        app.session.meeting.entries.append(Entry(12, "Committed fixture sentence."))
        app.session.accumulator.partial = ""
    app.transcript.update()
    app.transcript.update()
    text = app.transcript.text.get("1.0", "end")
    assert "Replacement hypothesis" not in text
    assert text.count("Committed fixture sentence.") == 1
    assert "00:00:10" in text
    app.transcript.query.set("fixture")
    assert len(app.transcript.text.tag_ranges("match")) == 4
    app.transcript.notes.insert("1.0", "Typed test note")
    app.sync_metadata()
    assert app.session.snapshot().notes == "Typed test note"
    assert not app.errors


def test_closing_transcript_only_hides_window(app):
    app.show_transcript()
    app.transcript.window.withdraw()
    pump(app)
    assert app.transcript.window.winfo_exists()
    assert not app.session.closed.is_set()


def test_quit_without_meeting_destroys_cleanly(app):
    app.quit()
    until(app.session.closed.is_set)
    app.poll()
    assert app.destroyed
    assert not app.errors


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_themes_render_and_controls_reflect_state(app, theme):
    app.palette = apply_theme(app.root, theme)
    app.show_transcript()
    for state in ("idle", "starting", "recording", "paused", "stopping", "stopped", "error"):
        app.widget.update(state, 3661)
        pump(app)
    assert not app.errors
