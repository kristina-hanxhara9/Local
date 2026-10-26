"""Phase 1: real PyAudio microphone -> official Foundry live session.

Run on Windows: python -m examples.microphone_sample
Adapted to fail clearly instead of the official example's synthetic fallback.
Microsoft reference:
https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/foundry-local/live-audio-transcription
"""
from __future__ import annotations

import queue
import threading

from meeting_companion.ai.foundry_client import FoundryClient
from meeting_companion.ai.live_transcriber import LiveTranscriber
from meeting_companion.config.settings import data_directory


def main():
    client = FoundryClient(data_directory() / "Foundry")
    transcriber = None
    pa = stream = None
    try:
        client.installed_contract()
        if input("Approve local model/runtime downloads if needed? [y/N] ").strip().lower() == "y":
            client.provision(lambda label, percent: print(f"\r{label}: {percent:.1f}%", end="", flush=True), threading.Event())
        else:
            client.load()
        if input("Allow live microphone capture under your employer's recording policy? [y/N] ").strip().lower() != "y":
            return 0
        import pyaudio

        def receive(text, final, start, end, identity):
            print(f"\r{'[FINAL]' if final else '[partial]'} {text}", end="\n" if final else "", flush=True)

        transcriber = LiveTranscriber(client.create_session(), receive)
        transcriber.start()
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000,
                         input=True, frames_per_buffer=1600)
        print("\nLIVE MICROPHONE — speak now. Ctrl+C stops capture. No audio files are written.")
        while True:
            if transcriber.error:
                raise RuntimeError(transcriber.error)
            pcm = stream.read(1600, exception_on_overflow=True)
            try:
                transcriber.audio.put(pcm, timeout=.5)
            except queue.Full as exc:
                raise RuntimeError("Inference cannot keep up with live audio.") from exc
    except KeyboardInterrupt:
        print("\nStopping…")
    except Exception as exc:
        print(f"\nMicrophone transcription failed: {exc}")
        return 1
    finally:
        if stream:
            stream.stop_stream()
            stream.close()
        if pa:
            pa.terminate()
        if transcriber:
            transcriber.stop()
        client.unload()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
