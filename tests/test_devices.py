"""Exercise callback/cleanup policy without importing the Windows extension."""
import queue
import time
from types import SimpleNamespace

import pytest

from meeting_companion.audio.devices import Device, WindowsAudio


class Stream:
    def __init__(self):
        self.closed = self.stopped = False

    def is_active(self):
        return True

    def stop_stream(self):
        self.stopped = True

    def close(self):
        self.closed = True


class Context:
    def __init__(self):
        self.options = None
        self.terminated = False
        self.stream = Stream()

    def is_format_supported(self, *args, **kwargs):
        return True

    def open(self, **kwargs):
        self.options = kwargs
        return self.stream

    def terminate(self):
        self.terminated = True


def audio():
    value = object.__new__(WindowsAudio)
    value.pa = SimpleNamespace(paInt16=8, paContinue=0, paAbort=2)
    value.context = Context()
    value.streams = []
    value.faults = queue.Queue(maxsize=4)
    value.clock_fallback = False
    return value


def test_callback_only_queues_timestamped_pcm_at_native_format():
    value = audio()
    packets = queue.Queue(2)
    device = Device(7, "WASAPI|Headphones", "Headphones", 48000, 2, True)
    value.open("computer", device, packets)
    options = value.context.options
    assert options["rate"] == 48000 and options["channels"] == 2
    assert options["input_device_index"] == 7 and options["start"] is False
    before = time.monotonic()
    assert options["stream_callback"](b"\0" * 3840, 960,
                                      {"current_time": 10.0, "input_buffer_adc_time": 9.98}, 0) == (None, 0)
    packet = packets.get_nowait()
    assert abs(packet.started - (before - .02)) < .02
    assert packet.pcm == b"\0" * 3840 and packet.source == "computer"


def test_full_callback_queue_aborts_and_reports_instead_of_blocking():
    value = audio()
    packets = queue.Queue(1)
    packets.put("already full")
    value.open("microphone", Device(0, "mic", "mic", 16000, 1, False), packets)
    callback = value.context.options["stream_callback"]
    before = time.monotonic()
    assert callback(b"\0" * 640, 320, {}, 0) == (None, 2)
    assert time.monotonic() - before < .1
    assert "queue filled" in value.faults.get_nowait()


def test_portaudio_overrun_is_not_silently_ignored():
    value = audio()
    value.open("microphone", Device(0, "mic", "mic", 16000, 1, False), queue.Queue(1))
    callback = value.context.options["stream_callback"]
    assert callback(b"\0" * 640, 320, {}, 2) == (None, 2)
    assert "overrun" in value.faults.get_nowait()


def test_arrival_clock_fallback_is_visible_to_pipeline():
    value = audio()
    packets = queue.Queue(1)
    value.open("microphone", Device(0, "mic", "mic", 16000, 1, False), packets)
    value.context.options["stream_callback"](b"\0" * 640, 320, {}, 0)
    assert value.clock_fallback


def test_close_releases_stream_and_terminates_context():
    value = audio()
    value.open("microphone", Device(0, "mic", "mic", 16000, 1, False), queue.Queue(1))
    stream = value.streams[0]
    value.close()
    assert stream.closed and stream.stopped and value.context.terminated
    assert value.streams == []


def test_device_open_error_names_the_failed_endpoint():
    value = audio()

    def fail(**kwargs):
        raise OSError("Unsupported format")

    value.context.open = fail
    with pytest.raises(RuntimeError, match="computer device 'Headphones'"):
        value.open("computer", Device(7, "headphones", "Headphones", 48000, 2, True), queue.Queue(1))
