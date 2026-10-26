from meeting_companion.services.transcript import TranscriptAccumulator


def test_partial_replaces_current_hypothesis_then_final_commits_once():
    transcript = TranscriptAccumulator()
    assert transcript.accept("hello", False, 0, None, "segment", 0, 2) is None
    assert transcript.accept("hello world", False, 0, None, "segment", 0, 2) is None
    assert transcript.partial == "hello world"
    result = transcript.accept("Hello world.", True, 0, 2, "segment", 10, 12)
    assert result.text == "Hello world."
    assert result.offset == 10
    assert result.end == 12
    assert transcript.partial == ""
    assert transcript.accept("Hello world.", True, 0, 2, "segment", 10, 12) is None


def test_repeated_real_words_in_different_segments_are_preserved():
    transcript = TranscriptAccumulator()
    a = transcript.accept("Yes", True, 0, 1, "a", 0, 1)
    b = transcript.accept("Yes", True, 2, 3, "b", 0, 3)
    assert a and b and a.offset != b.offset


def test_untimed_results_use_meeting_clock_and_empty_final_clears_partial():
    transcript = TranscriptAccumulator()
    result = transcript.accept("Speech", True, None, None, None, 5, 8)
    assert result.offset == 8
    transcript.partial = "uncertain"
    assert transcript.accept("", True, None, None, None, 5, 8) is None
    assert transcript.partial == ""


def test_timed_duplicate_without_id_is_not_added_twice():
    transcript = TranscriptAccumulator()
    assert transcript.accept("Speech", True, 1, 2, None, 0, 3)
    assert transcript.accept("Speech", True, 1, 2, None, 0, 3) is None


def test_invalid_sdk_timestamps_do_not_crash_exports():
    transcript = TranscriptAccumulator()
    result = transcript.accept("Speech", True, float("nan"), float("inf"), None, 0, 8)
    assert result.offset == 8 and result.end is None
