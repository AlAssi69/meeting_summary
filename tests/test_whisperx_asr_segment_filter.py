"""Tests for WhisperX post-ASR segment filtering."""

from __future__ import annotations

from meeting_assistant.services.whisperx_asr_segment_filter import filter_whisperx_asr_segments


def test_filter_drops_long_repetitive_segment() -> None:
    repetitive = "yes " * 80
    normal = "This is a normal sentence with varied vocabulary and structure."
    segments = [
        {"text": repetitive, "start": 0.0, "end": 1.0, "avg_logprob": -0.2},
        {"text": normal, "start": 1.0, "end": 3.0, "avg_logprob": -0.2},
    ]
    out = filter_whisperx_asr_segments(
        segments,
        compression_ratio_threshold=2.4,
        compression_min_chars=24,
        min_avg_logprob=None,
    )
    assert len(out) == 1
    assert out[0]["text"] == normal


def test_filter_keeps_short_repetitive_segment_below_min_chars() -> None:
    short = "yes yes yes"
    segments = [{"text": short, "start": 0.0, "end": 1.0, "avg_logprob": -0.2}]
    out = filter_whisperx_asr_segments(
        segments,
        compression_ratio_threshold=2.4,
        compression_min_chars=24,
        min_avg_logprob=None,
    )
    assert len(out) == 1


def test_filter_drops_low_avg_logprob_when_configured() -> None:
    segments = [
        {"text": "Some transcript text here.", "start": 0.0, "end": 1.0, "avg_logprob": -2.5},
        {"text": "Better confidence line here.", "start": 1.0, "end": 2.0, "avg_logprob": -0.3},
    ]
    out = filter_whisperx_asr_segments(
        segments,
        compression_ratio_threshold=10.0,
        compression_min_chars=1000,
        min_avg_logprob=-1.0,
    )
    assert len(out) == 1
    assert "Better confidence" in out[0]["text"]


def test_filter_skips_logprob_when_key_missing() -> None:
    segments = [{"text": "No avg_logprob key", "start": 0.0, "end": 1.0}]
    out = filter_whisperx_asr_segments(
        segments,
        compression_ratio_threshold=10.0,
        compression_min_chars=1000,
        min_avg_logprob=-0.5,
    )
    assert len(out) == 1


def test_filter_drops_empty_text() -> None:
    segments = [{"text": "   ", "start": 0.0, "end": 1.0, "avg_logprob": -0.2}]
    out = filter_whisperx_asr_segments(
        segments,
        compression_ratio_threshold=2.4,
        compression_min_chars=0,
        min_avg_logprob=None,
    )
    assert out == []
