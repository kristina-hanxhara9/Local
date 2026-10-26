from __future__ import annotations

import platform
import queue
import time
from dataclasses import dataclass

from .mixer import AudioPacket


@dataclass(frozen=True)
class Device:
    index: int
    key: str
    label: str
    rate: int
    channels: int
    loopback: bool


class WindowsAudio:
    """One PyAudioWPatch context covers both WASAPI microphone and loopback."""

    def __init__(self):
        if platform.system() != "Windows":
            raise RuntimeError("Live meeting capture requires Windows WASAPI. This computer is not Windows.")
        try:
            import pyaudiowpatch as pa
        except ImportError as exc:
            raise RuntimeError("Install PyAudioWPatch from requirements.txt on Windows.") from exc
        self.pa = pa
        self.context = pa.PyAudio()
        self.streams = []
        self.faults: queue.Queue[str] = queue.Queue(maxsize=4)
        self.clock_fallback = False

    def devices(self) -> tuple[list[Device], list[Device]]:
        microphones, computers = [], []
        for index in range(self.context.get_device_count()):
            info = self.context.get_device_info_by_index(index)
            host = self.context.get_host_api_info_by_index(int(info["hostApi"]))
            if int(host["type"]) != self.pa.paWASAPI or not info["maxInputChannels"]:
                continue
            loop = bool(info.get("isLoopbackDevice", False))
            device = Device(index, f'{host["name"]}|{info["name"]}', str(info["name"]),
                            int(info["defaultSampleRate"]), int(info["maxInputChannels"]), loop)
            (computers if loop else microphones).append(device)
        return microphones, computers

    def select(self, source: str, key: str = "") -> Device:
        microphones, computers = self.devices()
        pool = microphones if source == "microphone" else computers
        if key:
            matches = [d for d in pool if d.key == key]
            if len(matches) != 1:
                raise RuntimeError(f"The selected {source} device is missing or ambiguous. Select it again in Settings.")
            return matches[0]
        try:
            if source == "computer":
                info = self.context.get_default_wasapi_loopback()
                index = int(info["index"])
            else:
                host = self.context.get_host_api_info_by_type(self.pa.paWASAPI)
                index = int(host["defaultInputDevice"])
            return next(d for d in pool if d.index == index)
        except (OSError, LookupError, StopIteration, ValueError) as exc:
            raise RuntimeError(f"No default WASAPI {source} endpoint. Select a compatible device in Settings. "
                               "For headphones, select the endpoint used by your meeting application.") from exc

    def _fault(self, message: str) -> None:
        try:
            self.faults.put_nowait(message)
        except queue.Full:
            pass

    def open(self, source: str, device: Device, packets: queue.Queue) -> None:
        channels = 1 if source == "microphone" else device.channels
        try:
            self.context.is_format_supported(device.rate, input_device=device.index,
                                             input_channels=channels, input_format=self.pa.paInt16)
        except ValueError:
            channels = device.channels
        clock_offset = None

        def callback(data, frame_count, time_info, status):
            nonlocal clock_offset
            if status:
                self._fault(f"{source.capitalize()} capture overrun (PortAudio {status}). "
                            "The transcript may have a gap; stop and check device load.")
                return None, self.pa.paAbort
            now = time.monotonic()
            adc, current = time_info.get("input_buffer_adc_time", 0), time_info.get("current_time", 0)
            if current > 0 and adc > 0 and abs(current - adc) < 5:
                if clock_offset is None:
                    clock_offset = now - current
                started = adc + clock_offset
            else:
                self.clock_fallback = True
                started = now - frame_count / device.rate
            try:
                packets.put_nowait(AudioPacket(source, started, data, device.rate, channels))
            except queue.Full:
                self._fault("Audio processing queue filled. Capture stopped rather than silently dropping audio.")
                return None, self.pa.paAbort
            return None, self.pa.paContinue

        try:
            stream = self.context.open(format=self.pa.paInt16, channels=channels, rate=device.rate,
                                       input=True, input_device_index=device.index,
                                       frames_per_buffer=max(1, device.rate // 50),
                                       stream_callback=callback, start=False)
        except Exception as exc:
            raise RuntimeError(f"Cannot open {source} device '{device.label}': {exc}. "
                               "Check Windows microphone permission, exclusive-mode apps and the current "
                               "Bluetooth playback profile. Computer audio has not been substituted.") from exc
        self.streams.append(stream)

    def start(self) -> None:
        for stream in self.streams:
            stream.start_stream()

    def close(self) -> None:
        errors = []
        for stream in self.streams:
            try:
                if stream.is_active():
                    stream.stop_stream()
            except Exception as exc:
                errors.append(str(exc))
            finally:
                try:
                    stream.close()
                except Exception as exc:
                    errors.append(str(exc))
        self.streams.clear()
        try:
            self.context.terminate()
        finally:
            if errors:
                raise RuntimeError("Audio device cleanup reported: " + "; ".join(errors))
