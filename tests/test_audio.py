import numpy as np
import pytest

from meeting_companion.audio.mixer import AlignedMixer, AudioPacket, BLOCK, RATE, StreamingResampler, Timeline


def pcm(values):
    return np.asarray(values, dtype="<i2").tobytes()


@pytest.mark.parametrize("rate", [16000, 44100, 48000, 96000, 8000])
def test_resampler_preserves_count_and_phase_across_irregular_chunks(rate):
    signal = (np.sin(np.arange(rate * 2) * 2 * np.pi * 700 / rate) * 12000).astype("<i2")
    full = StreamingResampler(rate, 1).convert(signal.tobytes())[0]
    converter = StreamingResampler(rate, 1)
    parts = [converter.convert(part.tobytes())[0] for part in np.array_split(signal, 133)]
    streamed = np.concatenate(parts)
    assert abs(len(streamed) - RATE * 2) <= 2
    np.testing.assert_allclose(streamed, full, atol=1e-6)


def test_stereo_downmix_uses_float_not_overflowing_int16():
    converter = StreamingResampler(16000, 2)
    values, _ = converter.convert(pcm([[32000, 32000]] * 100))
    np.testing.assert_allclose(values, 32000 / 32768)


def test_resampling_rejects_partial_pcm_frame():
    with pytest.raises(ValueError):
        StreamingResampler(16000, 2).convert(pcm([100, 200, 300]))


def test_downsampling_rejects_above_nyquist():
    rate = 48000
    signal = (np.sin(np.arange(rate) * 2 * np.pi * 15000 / rate) * 20000).astype("<i2")
    output, _ = StreamingResampler(rate, 1).convert(signal.tobytes())
    assert np.sqrt(np.mean(output[1000:] ** 2)) < .02


def test_timestamps_align_overlapping_streams_instead_of_concatenating():
    mixer = AlignedMixer(("microphone", "computer"), 10, echo_reduction=False)
    mixer.ingest(AudioPacket("computer", 10.02, pcm([20000] * BLOCK), RATE, 1))
    mixer.ingest(AudioPacket("microphone", 10, pcm([10000] * (BLOCK * 2)), RATE, 1))
    first, _, coverage = mixer.render()
    np.testing.assert_array_equal(np.frombuffer(first, "<i2"), 5000)
    assert coverage == {"microphone": 1, "computer": 0}
    second, _, coverage = mixer.render()
    np.testing.assert_array_equal(np.frombuffer(second, "<i2"), 15000)
    assert coverage == {"microphone": 1, "computer": 1}


@pytest.mark.parametrize("value", [32767, -32768])
def test_combined_full_scale_never_wraps_or_clips(value):
    mixer = AlignedMixer(("microphone", "computer"), 0, echo_reduction=False)
    for source in mixer.sources:
        mixer.ingest(AudioPacket(source, 0, pcm([value] * BLOCK), RATE, 1))
    output, _, _ = mixer.render()
    np.testing.assert_array_equal(np.frombuffer(output, "<i2"), value)


def test_delayed_correlated_playback_bleed_is_reduced():
    rng = np.random.default_rng(4)
    playback = (rng.normal(size=BLOCK * 2) * 4000).astype("<i2")
    mixer = AlignedMixer(("microphone", "computer"), 0, echo_reduction=True)
    mixer.ingest(AudioPacket("computer", 0, playback.tobytes(), RATE, 1))
    mixer.ingest(AudioPacket("microphone", 0, pcm(np.r_[np.zeros(BLOCK), playback[:BLOCK] * .4]), RATE, 1))
    mixer.render()
    output, _, _ = mixer.render()
    assert mixer.echo_detected
    np.testing.assert_allclose(np.frombuffer(output, "<i2"), playback[BLOCK:] / 2, atol=2)


def test_timeline_wrap_and_missing_samples_are_explicit():
    timeline = Timeline(capacity=8)
    timeline.write(0, np.arange(8), 0)
    timeline.write(8, np.arange(10, 14), 4)
    values, coverage = timeline.read(4, 8)
    np.testing.assert_array_equal(values, [4, 5, 6, 7, 10, 11, 12, 13])
    assert coverage == 1
    _, coverage = timeline.read(12, 4)
    assert coverage == 0
    with pytest.raises(RuntimeError, match="clock"):
        timeline.write(20, np.ones(4), 0)


def test_late_samples_counted_and_not_replayed():
    timeline = Timeline(100)
    assert timeline.write(0, np.ones(20), 10) == 10
    _, covered = timeline.read(0, 10)
    assert covered == 0


def test_timestamp_alignment_at_different_device_rates():
    mixer = AlignedMixer(("microphone", "computer"), 100, echo_reduction=False)
    # Simulate a second of independently delivered native 44.1/48kHz blocks.
    for i in range(50):
        for source, rate in (("microphone", 44100), ("computer", 48000)):
            mixer.ingest(AudioPacket(source, 100 + i / 50, pcm([8000] * (rate // 50)), rate, 1))
    outputs = [mixer.render() for _ in range(49)]
    assert all(all(v > .98 for v in coverage.values()) for _, _, coverage in outputs)
    assert mixer.late_samples == 0


def test_device_format_change_fails_explicitly():
    mixer = AlignedMixer(("microphone",), 0)
    mixer.ingest(AudioPacket("microphone", 0, pcm([0] * 320), 16000, 1))
    with pytest.raises(RuntimeError, match="changed format"):
        mixer.ingest(AudioPacket("microphone", .02, pcm([0] * 960), 48000, 1))
