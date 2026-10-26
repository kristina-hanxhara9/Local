"""WASAPI loopback endpoint selection (includes compatible headphones)."""
from .devices import WindowsAudio


def select_loopback(audio: WindowsAudio, key: str = ""):
    return audio.select("computer", key)
