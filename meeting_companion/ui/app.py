from __future__ import annotations

import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from meeting_companion.config.settings import Settings, data_directory
from meeting_companion.services.meeting_session import BUSY, MeetingSession
from meeting_companion.services.reminders import Reminders
from meeting_companion.services.startup import set_startup
from meeting_companion.services.system_tray import SystemTray
from meeting_companion.services.transcript_storage import TranscriptStorage
from .history_window import HistoryWindow
from .settings_window import SettingsWindow
from .setup_window import SetupWindow
from .theme import apply_theme
from .transcript_window import TranscriptWindow
from .widget import Widget


class Application:
    def __init__(self, root, settings=None, tray_start=False):
        self.root = root
        self.settings = settings or Settings.load()
        data_directory().mkdir(parents=True, exist_ok=True)
        self.palette = apply_theme(root, self.settings.theme)
        self.session = MeetingSession(self.settings, TranscriptStorage(self.settings.directory))
        self.reminders = Reminders(self.settings)
        self.actions = queue.SimpleQueue()
        self.tray = SystemTray(self.actions.put)
        self.transcript = self.settings_window = self.setup_window = self.history = None
        self.quitting = False
        self.destroyed = False
        self.tray_state = None
        self.last_metadata = 0
        self.widget = Widget(self)
        self.root.geometry("370x340+80+80")
        try:
            self.tray.start()
        except Exception as exc:
            self.root.after(300, lambda error=str(exc): messagebox.showwarning(
                "Tray unavailable", f"The widget can still minimise to the taskbar. {error}", parent=root))
        if tray_start and self.settings.setup_complete:
            self.root.after(600, self.hide)
        if not self.settings.setup_complete:
            self.root.after(350, self.show_setup)
        self.root.after(100, self.poll)

    def show(self):
        self.root.deiconify()
        self.root.lift()

    def hide(self):
        if self.tray.ready.is_set():
            self.root.withdraw()
        else:
            self.root.iconify()

    def show_transcript(self):
        if self.transcript is None or not self.transcript.window.winfo_exists():
            self.transcript = TranscriptWindow(self)
        self.transcript.update()
        self.transcript.show()

    def show_history(self):
        if self.history and self.history.window.winfo_exists():
            self.history.refresh()
            self.history.window.lift()
        else:
            self.history = HistoryWindow(self)

    def show_settings(self):
        if self.settings_window and self.settings_window.window.winfo_exists():
            self.settings_window.window.lift()
        else:
            self.settings_window = SettingsWindow(self)

    def show_setup(self):
        if self.setup_window and self.setup_window.window.winfo_exists():
            self.setup_window.window.lift()
        else:
            self.setup_window = SetupWindow(self)

    def sync_metadata(self):
        if self.transcript and self.transcript.window.winfo_exists() and self.transcript.meeting_id:
            self.session.update_metadata(*self.transcript.metadata())

    def start(self, test=False):
        if self.session.state in BUSY or self.quitting:
            return
        previous = self.session.snapshot()
        save_previous = False
        if previous and not self.session.capture_settings.autosave:
            choice = messagebox.askyesnocancel("Keep the previous meeting?", "Save the previous meeting to History "
                                             "before starting a new one? Choose No to discard the in-memory copy.", parent=self.root)
            if choice is None:
                return
            if choice:
                self.sync_metadata()
                save_previous = True
        if not messagebox.askyesno("Allow live transcription?",
                                  f"Start {self.settings.mode.lower()} capture now?\n\n"
                                  "Loopback records all sounds on the selected playback device, including notifications. "
                                  "Audio is processed locally and is not saved as a recording.\n\n"
                                  "Make sure you have the consent required by your employer’s recording and privacy policies.",
                                  parent=self.root):
            return
        from dataclasses import replace
        title = "Setup transcription test" if test else "Untitled meeting"
        if not test and previous is None and self.transcript and self.transcript.window.winfo_exists():
            title = self.transcript.title.get()
        options = replace(self.settings, autosave=False) if test else self.settings
        if self.session.start(title, options, save_previous=save_previous):
            self.reminders.activity()
            self.show_transcript()
            if self.setup_window and self.setup_window.window.winfo_exists():
                self.setup_window.window.lower(self.transcript.window)

    def pause(self):
        self.sync_metadata()
        self.session.command("resume" if self.session.state == "paused" else "pause")

    def stop(self):
        self.sync_metadata()
        self.session.command("stop")

    def save(self):
        self.sync_metadata()
        if self.session.snapshot():
            self.session.command("save")

    def copy_transcript(self):
        self.sync_metadata()
        snapshot = self.session.snapshot()
        if snapshot:
            self.root.clipboard_clear()
            self.root.clipboard_append(snapshot.render())

    def export(self):
        self.sync_metadata()
        snapshot = self.session.snapshot()
        if not snapshot:
            return
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".txt",
                                          initialfile=f"meeting-{snapshot.started[:10]}.txt",
                                          filetypes=[("Text", "*.txt"), ("Markdown", "*.md")])
        if path:
            try:
                self.session.storage.export(snapshot, Path(path))
                self.widget.hint.configure(text="Transcript exported locally")
            except Exception as exc:
                messagebox.showerror("Export failed", str(exc), parent=self.root)

    def select_mode(self, mode):
        if self.session.state not in BUSY:
            self.settings.mode = mode
            self.settings.save()

    def apply_settings(self, settings):
        changing_storage = settings.directory != self.settings.directory
        changing_audio = any(getattr(settings, name) != getattr(self.settings, name)
                             for name in ("mode", "microphone", "loopback", "echo_reduction"))
        if changing_audio and self.session.state in BUSY:
            raise RuntimeError("Stop transcription and finish setup before changing audio devices, mode or echo reduction.")
        if changing_storage and self.session.state in BUSY:
            raise RuntimeError("Stop transcription and finish setup before changing the history folder.")
        if changing_storage:
            # Verify write access before committing any settings changes.
            TranscriptStorage(settings.directory)
        set_startup(settings.startup)
        settings.save()
        old_theme = self.settings.theme
        self.settings = self.session.settings = self.reminders.settings = settings
        self.session.command("preferences", settings)
        self.root.attributes("-topmost", settings.always_on_top)
        if changing_storage:
            self.session.command("storage", settings.directory)
        if settings.theme != old_theme:
            self.palette = apply_theme(self.root, settings.theme)
            # Rebuild Text controls with the new palette; preserve metadata in the session first.
            self.sync_metadata()
            if self.transcript and self.transcript.window.winfo_exists():
                self.transcript.window.destroy()
                self.transcript = None
                self.show_transcript()
            if self.history and self.history.window.winfo_exists():
                self.history.window.destroy()
                self.history = None
        if self.transcript and self.transcript.window.winfo_exists() and self.session.state not in BUSY:
            self.transcript.mode.set(settings.mode)

    def quit(self):
        if self.quitting:
            return
        self.sync_metadata()
        if self.session.state in BUSY and not messagebox.askyesno(
                "Quit Meeting Companion?", "Stop the active operation, release audio devices and quit?", parent=self.root):
            return
        snapshot = self.session.snapshot()
        save_on_quit = None
        if snapshot and (not self.session.capture_settings.autosave or self.session.last_save_error):
            save = messagebox.askyesnocancel("Save before quitting?", "Save this transcript and notes to local history?", parent=self.root)
            if save is None:
                return
            save_on_quit = save
        self.quitting = True
        self.session.command("shutdown", save_on_quit)
        self.widget.status.configure(text="FINISHING LOCAL INFERENCE…")

    def handle_event(self, kind, value):
        if self.setup_window and self.setup_window.window.winfo_exists():
            self.setup_window.event(kind, value)
        if kind == "error":
            self.show()
            self.widget.hint.configure(text="Check the error message before restarting")
            messagebox.showerror("Meeting Companion", value, parent=self.root)
        elif kind == "warning":
            self.widget.hint.configure(text="Audio alignment warning · See notification")
            self.tray.notify(value)
            messagebox.showwarning("Audio capture limitation", value, parent=self.root)
        elif kind == "devices":
            if self.settings_window and self.settings_window.window.winfo_exists():
                self.settings_window.set_devices(value)
        elif kind == "provisioned":
            self.settings.providers_provisioned = True
            self.settings.save()
        elif kind == "saved":
            self.widget.hint.configure(text="Saved to local History")
        elif kind == "levels":
            if self.transcript and self.transcript.window.winfo_exists():
                self.transcript.levels.configure(text="Input levels  ·  " + "  ·  ".join(
                    f"{source.capitalize()}: {min(100, rms * 300):.0f}%" for source, rms in value.items()))
        elif kind == "finished":
            self.tray.notify("Transcription stopped. Your transcript is ready to save or export.")
        elif kind == "quit_cancelled":
            self.quitting = False

    def poll(self):
        try:
            if self.quitting and self.session.closed.is_set():
                self.tray.stop()
                self.destroyed = True
                self.root.destroy()
                return
            for _ in range(20):
                try:
                    action = self.actions.get_nowait()
                except queue.Empty:
                    break
                {"show": self.show, "transcript": self.show_transcript, "start": self.start,
                 "pause": self.pause, "stop": self.stop, "quit": self.quit}[action]()
            for _ in range(20):
                try:
                    kind, value = self.session.events.get_nowait()
                except queue.Empty:
                    break
                self.handle_event(kind, value)
            with self.session.lock:
                latest, self.session.latest = self.session.latest, {}
            for kind, value in latest.items():
                self.handle_event(kind, value)
            self.widget.update(self.session.state, self.session.elapsed())
            if self.transcript and self.transcript.window.winfo_exists():
                self.transcript.update()
                self.sync_metadata()
            active = self.session.capture is not None or self.session.state == "testing"
            if active != self.tray_state:
                self.tray.active(active)
                self.tray_state = active
            if self.reminders.due(self.session.state in BUSY):
                self.tray.notify("Joining a meeting? Start your local transcription.")
                self.widget.hint.configure(text="Joining a meeting? Start local transcription.")
        except Exception as exc:
            # Keep the GUI event pump alive after a recoverable UI/storage error.
            self.widget.hint.configure(text=f"Interface error: {str(exc)[:60]}")
        finally:
            if not self.destroyed:
                self.root.after(150, self.poll)
