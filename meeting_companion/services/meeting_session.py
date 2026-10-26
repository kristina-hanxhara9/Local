from __future__ import annotations

import copy
import queue
import threading
import time
from dataclasses import replace

from meeting_companion.ai.foundry_client import FoundryClient
from meeting_companion.ai.live_transcriber import LiveTranscriber
from meeting_companion.audio.devices import WindowsAudio
from meeting_companion.audio.pipeline import AudioPipeline
from meeting_companion.config.settings import Settings, data_directory
from .models import Meeting
from .transcript import TranscriptAccumulator
from .transcript_storage import TranscriptStorage

BUSY = {"starting", "recording", "pausing", "paused", "resuming", "stopping", "setup", "checking", "testing"}


class MeetingSession:
    """One lifecycle worker serializes model, device and SQLite mutations."""

    def __init__(self, settings: Settings, storage: TranscriptStorage, client=None, pipeline_factory=AudioPipeline):
        self.settings, self.storage = settings, storage
        self.client = client or FoundryClient(data_directory() / "Foundry")
        self.pipeline_factory = pipeline_factory
        self.lock = threading.RLock()
        self.events: queue.Queue = queue.Queue(maxsize=128)
        self.commands: queue.Queue = queue.Queue()  # Infrequent UI commands must never drop Stop/Shutdown.
        self.latest = {}
        self.state = "idle"
        self.meeting: Meeting | None = None
        self.accumulator = TranscriptAccumulator()
        self.capture = self.transcriber = None
        self.started_clock = self.segment_offset = 0.0
        self.last_saved = 0.0
        self.capture_settings = settings
        self.cancel_setup = threading.Event()
        self.closed = threading.Event()
        self.shutting_down = False
        self.poisoned = False
        self.persist_on_finish = False
        self.last_save_error = None
        self.worker = threading.Thread(target=self._run, name="meeting-controller", daemon=True)
        self.worker.start()

    def notify(self, kind, value):
        if kind in ("levels", "progress"):
            with self.lock:
                self.latest[kind] = value
            return
        try:
            self.events.put_nowait((kind, value))
        except queue.Full:
            with self.lock:
                self.latest["error"] = "Too many notifications; open the transcript and check the meeting status."

    def _state(self, state):
        with self.lock:
            self.state = state
        self.notify("state", state)

    def start(self, title="Untitled meeting", settings=None, save_previous=False) -> bool:
        with self.lock:
            if self.state in BUSY or self.poisoned or self.shutting_down:
                return False
            self.state = "starting"
        self.notify("state", "starting")
        self.commands.put_nowait(("start", (title, copy.copy(settings or self.settings), save_previous)))
        return True

    def command(self, name: str, value=None) -> None:
        if name == "shutdown":
            self.cancel_setup.set()
        self.commands.put_nowait((name, value))

    def setup_task(self, name: str, value=None) -> bool:
        with self.lock:
            if self.state in BUSY or self.shutting_down:
                return False
            self.state = "setup" if name == "provision" else "checking"
        self.cancel_setup.clear()
        self.commands.put_nowait((name, value))
        return True

    def elapsed(self) -> float:
        with self.lock:
            if not self.meeting:
                return 0
            if self.state in {"recording", "paused", "pausing", "resuming", "stopping"}:
                return max(0, time.monotonic() - self.started_clock)
            return self.meeting.duration

    def update_metadata(self, title: str, notes: str) -> None:
        with self.lock:
            if self.meeting:
                self.meeting.title = title.strip() or "Untitled meeting"
                self.meeting.notes = notes

    def snapshot(self) -> Meeting | None:
        with self.lock:
            if self.meeting is None:
                return None
            return replace(self.meeting, entries=list(self.meeting.entries), duration=self.elapsed())

    def changes(self, after: int) -> tuple:
        with self.lock:
            return (self.meeting.id if self.meeting else None,
                    self.meeting.entries[after:] if self.meeting else [], self.accumulator.partial,
                    self.state, self.elapsed())

    def _receive(self, *args):
        with self.lock:
            if self.meeting is None:
                return
            entry = self.accumulator.accept(*args, self.segment_offset, self.elapsed())
            if entry:
                self.meeting.entries.append(entry)

    def _open_capture(self):
        self.accumulator = TranscriptAccumulator()
        self.segment_offset = max(0, time.monotonic() - self.started_clock)
        self.transcriber = LiveTranscriber(self.client.create_session(), self._receive)
        self.transcriber.start()
        self.capture = self.pipeline_factory(self.capture_settings, self.transcriber.audio, self.notify)
        self.capture.start()
        # The SDK receives audio starting at capture epoch, not model loading time.
        self.segment_offset = max(0, self.capture.epoch - self.started_clock)

    def _close_capture(self):
        errors = []
        if self.capture:
            try:
                self.capture.stop()
            except Exception as exc:
                self.poisoned = True
                errors.append(str(exc))
            self.capture = None
        if self.transcriber:
            try:
                self.transcriber.stop()
            except Exception as exc:
                self.poisoned = True
                errors.append(str(exc))
            self.transcriber = None
        with self.lock:
            self.accumulator.partial = ""
        if errors:
            raise RuntimeError("; ".join(errors))

    def _save(self):
        snapshot = self.snapshot()
        if snapshot:
            self.storage.save(snapshot)
            self.persist_on_finish = True
            self.last_save_error = None
            self.last_saved = time.monotonic()

    def _finish(self, failed=False):
        self._state("stopping")
        try:
            self._close_capture()
        except Exception as exc:
            failed = True
            self.notify("error", str(exc))
        with self.lock:
            if self.meeting:
                self.meeting.duration = time.monotonic() - self.started_clock
                self.meeting.status = "interrupted" if failed else "completed"
        self._state("error" if failed else "stopped")
        if self.capture_settings.autosave or self.persist_on_finish:
            try:
                self._save()
            except Exception as exc:
                self.last_save_error = str(exc)
                self.notify("error", f"Autosave failed. Export this meeting before exiting: {exc}")
        self.notify("finished", None)

    def _handle(self, name, value):
        if name == "start":
            title, options, save_previous = value
            if save_previous:
                try:
                    self._save()
                except Exception:
                    self._state("stopped")
                    raise
            self.capture_settings = options
            self.persist_on_finish = False
            self.last_save_error = None
            with self.lock:
                self.meeting = Meeting(title=title.strip() or "Untitled meeting", mode=self.capture_settings.mode)
                self.accumulator = TranscriptAccumulator()
                self.started_clock = time.monotonic()
            self.last_saved = time.monotonic()
            self._open_capture()
            self._state("recording")
        elif name == "pause" and self.state == "recording":
            self._state("pausing")
            self._close_capture()
            self._state("paused")
        elif name == "resume" and self.state == "paused":
            self._state("resuming")
            self._open_capture()
            self._state("recording")
        elif name == "stop" and self.state in {"recording", "paused"}:
            self._finish()
        elif name == "save":
            try:
                self._save()
                self.notify("saved", None)
            except Exception as exc:
                self.last_save_error = str(exc)
                self.notify("error", f"Save failed. Your in-memory transcript is still available; use Export: {exc}")
        elif name == "storage":
            if self.state in BUSY:
                raise RuntimeError("Stop the meeting before changing the storage location.")
            self.storage = TranscriptStorage(value)
            self.notify("storage", self.storage)
        elif name == "preferences":
            if self.state in {"recording", "paused"}:
                self.capture_settings = replace(self.capture_settings, autosave=value.autosave)
        elif name == "check_model":
            self.notify("model", self.client.check())
            self._state("idle")
        elif name == "provision":
            self.client.provision(lambda label, percent: self.notify("progress", (label, percent)), self.cancel_setup)
            self.notify("provisioned", None)
            self._state("idle")
        elif name == "devices":
            audio = WindowsAudio()
            try:
                self.notify("devices", audio.devices())
            finally:
                audio.close()
            self._state("idle")
        elif name == "audio_test":
            self._state("testing")
            output = queue.Queue(maxsize=80)
            capture = self.pipeline_factory(value, output, self.notify)
            try:
                capture.start()
                deadline = time.monotonic() + 4
                chunks = 0
                while time.monotonic() < deadline and not self.cancel_setup.is_set():
                    try:
                        output.get(timeout=.05)
                        chunks += 1
                    except queue.Empty:
                        pass
                    if capture.error:
                        raise RuntimeError(capture.error)
                if self.cancel_setup.is_set():
                    raise RuntimeError("Audio test cancelled.")
                if not chunks:
                    raise RuntimeError("No PCM audio was delivered by this device during the test.")
            finally:
                capture.stop()
            self.notify("tested", value.mode)
            self._state("idle")
        elif name == "shutdown":
            self.shutting_down = True
            if self.capture or self.state == "paused":
                self._finish()
            if value or (value is None and self.last_save_error):
                try:
                    self._save()
                except Exception as exc:
                    self.shutting_down = False
                    self.notify("quit_cancelled", None)
                    self.notify("error", f"Quit cancelled because saving failed. Export the transcript or fix local storage "
                                f"before exiting: {exc}")
                    return
            if not self.poisoned:
                self.client.unload()
            self.closed.set()

    def _run(self):
        while not self.closed.is_set():
            try:
                try:
                    name, value = self.commands.get(timeout=.1)
                except queue.Empty:
                    name = None
                if name:
                    self._handle(name, value)
                if self.state == "recording":
                    error = self.capture.error or self.transcriber.error
                    if error:
                        self.notify("error", error)
                        self._finish(failed=True)
                if (self.state in {"recording", "paused"} and self.capture_settings.autosave
                        and time.monotonic() - self.last_saved >= 5):
                    try:
                        self._save()
                    except Exception as exc:
                        self.last_saved = time.monotonic() + 25
                        self.last_save_error = str(exc)
                        self.notify("error", f"Autosave failed; use Save or Export: {exc}")
            except Exception as exc:
                self.notify("error", str(exc))
                if self.capture or self.transcriber or self.state in {"starting", "resuming", "pausing"}:
                    self._finish(failed=True)
                else:
                    self._state("error")
                if self.shutting_down:
                    self.closed.set()
