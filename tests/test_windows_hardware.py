"""Manual, opt-in acceptance tests. No downloads and no saved raw audio.

Speak into the microphone, or have a remote meeting participant speak through
the selected playback endpoint during the corresponding 12-second test.
"""
import platform
import time

import pytest

from meeting_companion.ai.foundry_client import FoundryClient
from meeting_companion.ai.live_transcriber import LiveTranscriber
from meeting_companion.audio.pipeline import AudioPipeline
from meeting_companion.config.settings import Settings, data_directory

pytestmark = [pytest.mark.windows, pytest.mark.hardware,
              pytest.mark.skipif(platform.system() != "Windows", reason="Windows hardware is unavailable")]


@pytest.mark.parametrize("mode", ["Microphone only", "Computer audio only", "Both"])
def test_real_live_speech_becomes_foundry_text(mode):
    settings = Settings.load()
    settings.mode = mode
    settings.autosave = False
    results = []
    client = FoundryClient(data_directory() / "Foundry")
    capture = transcriber = None
    try:
        client.load()  # Uncached models fail here; never downloads without setup approval.
        transcriber = LiveTranscriber(client.create_session(), lambda *value: results.append(value))
        transcriber.start()
        capture = AudioPipeline(settings, transcriber.audio, lambda kind, value: print(kind, value) if kind == "warning" else None)
        print(f"\nLIVE CAPTURE: {mode}. Speak now / ask the remote participant to speak. 12 seconds.")
        capture.start()
        end = time.monotonic() + 12
        while time.monotonic() < end:
            assert not capture.error, capture.error
            assert not transcriber.error, transcriber.error
            time.sleep(.05)
        capture.stop()
        capture = None
        transcriber.stop()
        transcriber = None
        assert any(text.strip() and final for text, final, *_ in results), "No real speech was recognised"
        print("Actual local model output:", [value[0] for value in results if value[1]])
    finally:
        if capture:
            capture.stop()
        if transcriber:
            transcriber.stop()
        client.unload()
