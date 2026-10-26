"""The final app uses PyAudioWPatch for both endpoints; the sample uses PyAudio."""
from .devices import WindowsAudio


def select_microphone(audio: WindowsAudio, key: str = ""):
    return audio.select("microphone", key)
