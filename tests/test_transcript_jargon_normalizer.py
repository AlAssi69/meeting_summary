"""Tests for diarized-prefix preservation and optional jargon normalization."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from meeting_assistant import config
from meeting_assistant.services.prompt_composition import PipelinePromptContext
from meeting_assistant.services.transcript_jargon_normalizer import (
    _is_probably_diarized,
    _prefix_through_first_bracket_colon,
    _structure_preserved,
    maybe_normalize_transcript,
    normalize_transcript_with_glossary,
)


def test_prefix_regex_diarized_line() -> None:
    line = "SPEAKER_00 [01:02 - 01:08]: كالمان filter"
    assert _prefix_through_first_bracket_colon(line) == "SPEAKER_00 [01:02 - 01:08]: "


def test_prefix_regex_hour_format() -> None:
    line = "SPEAKER_01 [01:02:03 - 01:08:09]: hello"
    assert _prefix_through_first_bracket_colon(line) == "SPEAKER_01 [01:02:03 - 01:08:09]: "


def test_is_probably_diarized() -> None:
    assert _is_probably_diarized("SPEAKER_00 [00:00 - 00:01]: hi")
    assert not _is_probably_diarized("plain text without markers")


def test_structure_preserved_ok_when_body_changes() -> None:
    orig = "SPEAKER_00 [00:00 - 00:01]: foo\nSPEAKER_01 [00:01 - 00:02]: bar"
    new = "SPEAKER_00 [00:00 - 00:01]: foo2\nSPEAKER_01 [00:01 - 00:02]: bar"
    assert _structure_preserved(orig, new)


def test_structure_preserved_rejects_line_count() -> None:
    orig = "SPEAKER_00 [00:00 - 00:01]: a"
    new = "SPEAKER_00 [00:00 - 00:01]: a\nSPEAKER_01 [00:01 - 00:02]: b"
    assert not _structure_preserved(orig, new)


def test_structure_preserved_rejects_prefix_tamper() -> None:
    orig = "SPEAKER_00 [00:00 - 00:01]: ok"
    new = "SPEAKER_99 [00:00 - 00:01]: ok"
    assert not _structure_preserved(orig, new)


def test_maybe_normalize_skips_without_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "TRANSCRIPT_JARGON_NORMALIZE", False)
    ctx = PipelinePromptContext(
        global_llm_system="",
        recording_llm_instructions="",
        global_whisper_context="Kalman",
        recording_whisper_context="",
    )
    t = "SPEAKER_00 [00:00 - 00:01]: كالمان"
    assert maybe_normalize_transcript(t, ctx) == t


def test_maybe_normalize_skips_empty_glossary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "TRANSCRIPT_JARGON_NORMALIZE", True)
    ctx = PipelinePromptContext(
        global_llm_system="",
        recording_llm_instructions="",
        global_whisper_context="   ",
        recording_whisper_context="",
    )
    t = "SPEAKER_00 [00:00 - 00:01]: x"
    assert maybe_normalize_transcript(t, ctx) == t


def test_normalize_transcript_with_glossary_mocked() -> None:
    orig = "SPEAKER_00 [00:00 - 00:01]: كالمان"

    def fake_chat(system: str, user: str) -> str:
        assert "Kalman" in user or "Glossary" in system
        return "SPEAKER_00 [00:00 - 00:01]: Kalman"

    with patch(
        "meeting_assistant.services.transcript_jargon_normalizer._ollama_chat",
        side_effect=fake_chat,
    ):
        out = normalize_transcript_with_glossary(orig, "Kalman filter")
    assert out == "SPEAKER_00 [00:00 - 00:01]: Kalman"


def test_maybe_normalize_falls_back_on_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "TRANSCRIPT_JARGON_NORMALIZE", True)
    monkeypatch.setattr(config, "USE_MOCK_BACKEND", False)
    ctx = PipelinePromptContext(
        global_llm_system="",
        recording_llm_instructions="",
        global_whisper_context="Kalman",
        recording_whisper_context="",
    )
    orig = "SPEAKER_00 [00:00 - 00:01]: كالمان"

    def bad_chat(system: str, user: str) -> str:
        return "broken"

    with patch(
        "meeting_assistant.services.transcript_jargon_normalizer._ollama_chat",
        side_effect=bad_chat,
    ):
        assert maybe_normalize_transcript(orig, ctx) == orig
