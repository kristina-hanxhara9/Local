from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, correlate, sosfilt, sosfilt_zi

RATE = 16000
BLOCK = 320  # 20 ms


@dataclass(frozen=True)
class AudioPacket:
    source: str
    started: float  # ADC time translated to the shared monotonic clock.
    pcm: bytes
    rate: int
    channels: int


class StreamingResampler:
    """Continuous sample phase + stateful anti-alias filter across callbacks.

    Input device timestamps determine placement, so independent device clock drift
    does not accumulate into an ever-growing alignment error. The small IIR group
    delay is not acoustic echo cancellation or hardware latency calibration.
    """

    def __init__(self, rate: int, channels: int):
        self.rate, self.channels = rate, channels
        self.count = 0
        self.output_count = 0
        self.previous = 0.0
        self.sos = butter(8, min(7200, rate * .44), fs=rate, output="sos") if rate > RATE else None
        self.zi = None

    def convert(self, pcm: bytes) -> tuple[np.ndarray, float]:
        samples = np.frombuffer(pcm, dtype="<i2")
        if len(samples) % self.channels:
            raise ValueError("Audio callback returned an incomplete PCM frame.")
        samples = samples.reshape(-1, self.channels).astype(np.float64).mean(axis=1) / 32768.0
        if not len(samples):
            return np.zeros(0, dtype=np.float32), 0.0
        if self.sos is not None:
            if self.zi is None:
                self.zi = sosfilt_zi(self.sos) * samples[0]
            samples, self.zi = sosfilt(self.sos, samples, zi=self.zi)
        # Produce only points with both neighbours already available.
        start_position = self.output_count * self.rate / RATE
        output_end = math.floor((self.count + len(samples) - 1) * RATE / self.rate) + 1
        positions = np.arange(self.output_count, output_end, dtype=np.float64) * self.rate / RATE
        input_positions = np.arange(self.count - 1, self.count + len(samples))
        values = np.concatenate(([self.previous], samples))
        converted = np.interp(positions, input_positions, values).astype(np.float32)
        relative_start = (start_position - self.count) / self.rate
        self.previous = float(samples[-1])
        self.count += len(samples)
        self.output_count = output_end
        return converted, relative_start


class Timeline:
    def __init__(self, capacity: int = RATE * 4):
        self.capacity = capacity
        self.values = np.zeros(capacity, dtype=np.float32)
        self.positions = np.full(capacity, -1, dtype=np.int64)

    def write(self, start: int, samples: np.ndarray, cursor: int) -> int:
        end = start + len(samples)
        lost = max(0, min(cursor, end) - max(0, start))
        low, high = max(cursor, start), min(end, cursor + self.capacity)
        if high > low:
            positions = np.arange(low, high)
            indices = positions % self.capacity
            self.values[indices] = samples[low - start:high - start]
            self.positions[indices] = positions
        if end > cursor + self.capacity:
            raise RuntimeError("Audio clock is outside the alignment buffer. Re-select both devices and retry.")
        return lost

    def read(self, start: int, length: int) -> tuple[np.ndarray, float]:
        positions = np.arange(start, start + length)
        indices = positions % self.capacity
        valid = self.positions[indices] == positions
        return np.where(valid, self.values[indices], 0), float(np.mean(valid))


class AlignedMixer:
    def __init__(self, sources: tuple[str, ...], epoch: float, echo_reduction: bool = True):
        self.sources = sources
        self.epoch = epoch
        self.cursor = 0
        self.buffers = {s: Timeline() for s in sources}
        self.converters: dict[str, StreamingResampler] = {}
        self.late_samples = 0
        self.echo_reduction = echo_reduction
        self.playback_history = np.zeros(RATE // 5, dtype=np.float32)
        self.echo_detected = False

    def ingest(self, packet: AudioPacket) -> None:
        if packet.source not in self.converters:
            self.converters[packet.source] = StreamingResampler(packet.rate, packet.channels)
        converter = self.converters[packet.source]
        if (converter.rate, converter.channels) != (packet.rate, packet.channels):
            raise RuntimeError("An audio device changed format during capture. Stop and select the new device.")
        samples, relative = converter.convert(packet.pcm)
        position = round((packet.started + relative - self.epoch) * RATE)
        self.late_samples += self.buffers[packet.source].write(position, samples, self.cursor)

    def render(self, length: int = BLOCK) -> tuple[bytes, dict[str, float], dict[str, float]]:
        blocks, levels, coverage = {}, {}, {}
        for source in self.sources:
            blocks[source], coverage[source] = self.buffers[source].read(self.cursor, length)
            levels[source] = float(np.sqrt(np.mean(blocks[source] ** 2)))
        if len(blocks) == 2:
            mic, playback = blocks["microphone"], blocks["computer"]
            history = np.concatenate((self.playback_history, playback))
            self.echo_detected = False
            if self.echo_reduction and np.dot(mic, mic) > 1e-5:
                # Conservative duplicate-waveform gate, with up to 200ms playback delay.
                # Double-talk generally lowers correlation; preserve the microphone then.
                dots = correlate(history, mic, mode="valid", method="fft")
                energy = np.convolve(history ** 2, np.ones(length), mode="valid")
                scores = dots / np.sqrt(np.maximum(energy * np.dot(mic, mic), 1e-12))
                best = int(np.argmax(scores))
                if scores[best] > .94 and energy[best] > 1e-5:
                    reference = history[best:best + length]
                    gain = float(dots[best] / energy[best])
                    if .05 < gain < 2.0:
                        mic = mic - gain * reference
                        self.echo_detected = True
            self.playback_history = history[-RATE // 5:]
            mixed = (mic + playback) * .5  # Fixed headroom; never sum int16 arrays.
        else:
            mixed = next(iter(blocks.values()))
        self.cursor += length
        pcm = (np.clip(mixed, -1, 32767 / 32768) * 32768).round().astype("<i2").tobytes()
        return pcm, levels, coverage
