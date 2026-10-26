from __future__ import annotations

import queue
import threading


class LiveTranscriber:
    """Separate bounded audio feeder and SDK result consumer. Tk is never touched."""

    def __init__(self, session, receive):
        self.session = session
        self.receive = receive
        self.audio: queue.Queue = queue.Queue(maxsize=80)
        self.error: str | None = None
        self.feeder = None
        self.reader = None
        self.stopping = False

    def start(self) -> None:
        self.session.start()
        self.reader = threading.Thread(target=self._read, name="foundry-results", daemon=True)
        self.feeder = threading.Thread(target=self._feed, name="foundry-audio-feed", daemon=True)
        self.reader.start()
        self.feeder.start()

    def _read(self) -> None:
        try:
            for result in self.session.get_stream():
                text = "".join(part.text or "" for part in result.content).strip() if result.content else ""
                self.receive(text, result.is_final, result.start_time, result.end_time, result.id)
            if not self.stopping:
                self.error = "The local transcription stream ended unexpectedly. Capture has been stopped."
        except Exception as exc:
            self.error = f"Local transcription interrupted: {exc}"

    def _feed(self) -> None:
        try:
            while True:
                pcm = self.audio.get()
                if pcm is None:
                    break
                self.session.append(pcm)
        except Exception as exc:
            self.error = f"Could not send live PCM audio to the local model: {exc}"

    def stop(self) -> None:
        self.stopping = True
        if self.feeder and self.feeder.is_alive():
            self.audio.put(None, timeout=5)
            self.feeder.join(timeout=10)
            if self.feeder.is_alive():
                raise RuntimeError("Foundry audio append is stalled. Audio capture is closed, but local inference "
                                   "is still stopping. Restart the application if it does not recover.")
        self.session.stop()  # Flushes native tail results before get_stream completes.
        if self.reader:
            self.reader.join(timeout=10)
            if self.reader.is_alive():
                raise RuntimeError("The Foundry result reader did not stop. Restart the application.")
