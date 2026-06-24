from meeting_assistant.services.diarization_format import (
    format_aligned_transcript,
    format_diarized_transcript,
    format_timestamp,
    normalize_segment_speakers,
)


def test_format_timestamp_under_hour() -> None:
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(15.4) == "00:15"
    assert format_timestamp(65) == "01:05"


def test_format_timestamp_over_hour() -> None:
    assert format_timestamp(3600) == "01:00:00"
    assert format_timestamp(3665) == "01:01:05"


def test_format_diarized_transcript_lines() -> None:
    segments = [
        {"speaker": "SPEAKER_00", "start": 0, "end": 15, "text": "Hello."},
        {"speaker": "SPEAKER_01", "start": 15, "end": 22, "text": "Hi there."},
    ]
    out = format_diarized_transcript(segments)
    blocks = [b.strip() for b in out.split("\n\n") if b.strip()]
    assert blocks[0] == "SPEAKER_00 [00:00 - 00:15]: Hello."
    assert blocks[1] == "SPEAKER_01 [00:15 - 00:22]: Hi there."


def test_normalize_arbitrary_labels() -> None:
    segments = [
        {"speaker": "A", "start": 0, "end": 1, "text": "x"},
        {"speaker": "B", "start": 1, "end": 2, "text": "y"},
        {"speaker": "A", "start": 2, "end": 3, "text": "z"},
    ]
    normalize_segment_speakers(segments)
    assert segments[0]["speaker"] == "SPEAKER_00"
    assert segments[1]["speaker"] == "SPEAKER_01"
    assert segments[2]["speaker"] == "SPEAKER_00"


def test_format_aligned_transcript_lines() -> None:
    segments = [
        {"start": 0, "end": 15, "text": "Hello."},
        {"start": 15, "end": 22, "text": "Hi there."},
    ]
    out = format_aligned_transcript(segments)
    assert "SPEAKER_" not in out
    blocks = [b.strip() for b in out.split("\n\n") if b.strip()]
    assert blocks[0] == "[00:00 - 00:15]: Hello."
    assert blocks[1] == "[00:15 - 00:22]: Hi there."


def test_format_aligned_transcript_empty() -> None:
    assert format_aligned_transcript([]) == "(No speech detected)"
    assert format_aligned_transcript([{"start": 0, "end": 1, "text": ""}]) == "(No speech detected)"
