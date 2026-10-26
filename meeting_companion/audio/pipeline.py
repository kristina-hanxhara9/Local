from __future__ import annotations

import queue
import threading
import time

from meeting_companion.config.settings import Settings
from .devices import WindowsAudio
from .mixer import AlignedMixer, BLOCK, RATE


class AudioPipeline:
    def __init__(self, settings: Settings, output: queue.Queue, notify, audio_factory=WindowsAudio):
        self.settings, self.output, self.notify = settings, output, notify
        self.audio_factory = audio_factory
        self.audio = None
        self.packets = queue.Queue(maxsize=160)
        self.halt = threading.Event()
        self.thread = None
        self.error = None
        self.epoch = 0.0

    def start(self) -> None:
        self.audio = self.audio_factory()
        try:
            sources = []
            if self.settings.mode != "Computer audio only":
                sources.append("microphone")
                self.audio.open("microphone", self.audio.select("microphone", self.settings.microphone), self.packets)
            if self.settings.mode != "Microphone only":
                sources.append("computer")
                self.audio.open("computer", self.audio.select("computer", self.settings.loopback), self.packets)
            self.epoch = time.monotonic()
            self.mixer = AlignedMixer(tuple(sources), self.epoch, self.settings.echo_reduction)
            self.audio.start()
            self.thread = threading.Thread(target=self._run, name="audio-align-mix", daemon=True)
            self.thread.start()
        except Exception:
            self.audio.close()
            self.audio = None
            raise

    def _run(self) -> None:
        last_packet = {s: self.epoch for s in self.mixer.sources}
        missing = {s: 0 for s in self.mixer.sources}
        warned_clock = False
        try:
            while not self.halt.is_set():
                try:
                    fault = self.audio.faults.get_nowait()
                except queue.Empty:
                    pass
                else:
                    raise RuntimeError(fault)
                try:
                    packet = self.packets.get(timeout=.01)
                    self.mixer.ingest(packet)
                    last_packet[packet.source] = time.monotonic()
                    for _ in range(31):
                        try:
                            packet = self.packets.get_nowait()
                        except queue.Empty:
                            break
                        self.mixer.ingest(packet)
                        last_packet[packet.source] = time.monotonic()
                except queue.Empty:
                    pass
                now = time.monotonic()
                if self.audio.clock_fallback and not warned_clock:
                    self.notify("warning", "Device ADC timestamps are unavailable. Alignment uses arrival time; "
                                "simultaneous capture may be less accurate on this hardware.")
                    warned_clock = True
                for source, last in last_packet.items():
                    if now - last > 5:
                        raise RuntimeError(f"No {source} audio callbacks for five seconds. The device may have "
                                           "disconnected or stopped delivering silence. Check the selected endpoint "
                                           "and test it in Setup; both streams cannot be verified on this hardware.")
                # A 240 ms jitter buffer gives the two device callbacks time to align.
                while (self.mixer.cursor + BLOCK) / RATE < now - self.epoch - .24:
                    pcm, levels, coverage = self.mixer.render()
                    for source in missing:
                        missing[source] = missing[source] + 1 if coverage[source] < .8 else 0
                        if missing[source] >= 100:
                            raise RuntimeError(f"The {source} stream could not be aligned for two seconds. "
                                               "Use another device or capture mode; this transcript may have gaps.")
                    if self.mixer.late_samples > RATE // 4:
                        raise RuntimeError("Devices delivered audio too late to align reliably. "
                                           "Use wired headphones or select a different device pair.")
                    try:
                        self.output.put_nowait(pcm)
                    except queue.Full as exc:
                        raise RuntimeError("Local inference fell behind live audio. Capture stopped to prevent "
                                           "unbounded buffering; the last transcript segment may be incomplete.") from exc
                    if self.mixer.cursor % (BLOCK * 5) == 0:
                        self.notify("levels", levels)
        except Exception as exc:
            self.error = str(exc)
            self.halt.set()

    def stop(self) -> None:
        end_time = time.monotonic()
        self.halt.set()
        if self.thread:
            self.thread.join(timeout=3)
            if self.thread.is_alive():
                raise RuntimeError("Audio processing did not stop. Restart the application before capturing again.")
        if self.audio:
            try:
                self.audio.close()
            finally:
                self.audio = None
        # Flush the final jitter-buffered tail after all callbacks are closed.
        if self.thread and not self.error:
            while True:
                try:
                    self.mixer.ingest(self.packets.get_nowait())
                except queue.Empty:
                    break
            end = round((end_time - self.epoch) * RATE)
            while self.mixer.cursor < end:
                pcm, _, _ = self.mixer.render(min(BLOCK, end - self.mixer.cursor))
                try:
                    self.output.put(pcm, timeout=2)
                except queue.Full as exc:
                    raise RuntimeError("Inference stalled while flushing audio; final audio may be incomplete.") from exc
