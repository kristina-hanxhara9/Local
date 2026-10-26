import platform
from unittest.mock import patch

import pytest

from meeting_companion.ai.foundry_client import FoundryClient, ProvisioningRequired
from meeting_companion.ai.live_transcriber import LiveTranscriber
from tests.fakes import FakeSDKSession, until


def test_streaming_feeder_sends_pcm_and_drains_stop_tail():
    session = FakeSDKSession()
    results = []
    transcriber = LiveTranscriber(session, lambda *args: results.append(args))
    transcriber.start()
    transcriber.audio.put(b"\0" * 640)
    session.emit("Partial fixture", final=False)
    until(lambda: len(session.chunks) == 1)
    transcriber.stop()
    assert session.chunks == [b"\0" * 640]
    assert results[-1][0] == "Tail fixture"
    assert not transcriber.reader.is_alive() and not transcriber.feeder.is_alive()


def test_native_error_does_not_generate_a_transcript():
    session = FakeSDKSession()
    results = []
    transcriber = LiveTranscriber(session, lambda *args: results.append(args))
    transcriber.start()
    session.results.put(RuntimeError("Inference failed"))
    until(lambda: transcriber.error is not None)
    assert results == []
    transcriber.stop()


def test_non_windows_failure_is_actionable():
    with patch("platform.system", return_value="Darwin"):
        with pytest.raises(RuntimeError, match="Windows 11"):
            FoundryClient.installed_contract()


def test_uncached_model_never_downloads_implicitly(tmp_path):
    class Model:
        is_cached = False

        def download(self, *_):
            pytest.fail("No implicit download is allowed")

    client = FoundryClient(tmp_path)
    client.model = Model()
    with pytest.raises(ProvisioningRequired):
        client.load()


@pytest.mark.windows
@pytest.mark.skipif(platform.system() != "Windows", reason="Installed WinML SDK contract requires Windows")
def test_installed_windows_sdk_has_documented_native_streaming_methods():
    assert FoundryClient.installed_contract()["sdk"] == "1.2.4"
