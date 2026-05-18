"""Unit tests for prompt composition (Whisper + LLM)."""

from __future__ import annotations

import unittest

from meeting_assistant.services.prompt_composition import (
    WHISPER_INITIAL_PROMPT_MAX_CHARS,
    PipelinePromptContext,
    compose_llm_system_prompt,
    compose_llm_user_content,
    compose_whisper_initial_prompt,
)


class TestPromptComposition(unittest.TestCase):
    def test_whisper_none_when_empty(self) -> None:
        ctx = PipelinePromptContext("", "", "", "")
        self.assertIsNone(compose_whisper_initial_prompt(ctx))

    def test_whisper_joins_global_then_recording(self) -> None:
        ctx = PipelinePromptContext(
            global_llm_system="x",
            recording_llm_instructions="y",
            global_whisper_context="G",
            recording_whisper_context="R",
        )
        out = compose_whisper_initial_prompt(ctx)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertIn("G", out)
        self.assertIn("R", out)

    def test_whisper_truncation_keeps_suffix(self) -> None:
        long_g = "A" * (WHISPER_INITIAL_PROMPT_MAX_CHARS + 500)
        ctx = PipelinePromptContext(
            global_llm_system="",
            recording_llm_instructions="",
            global_whisper_context=long_g,
            recording_whisper_context="REC_TAIL",
        )
        out = compose_whisper_initial_prompt(ctx)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertLessEqual(len(out), WHISPER_INITIAL_PROMPT_MAX_CHARS)
        self.assertTrue(out.endswith("REC_TAIL"), out[-80:])

    def test_llm_system_recording_optional(self) -> None:
        ctx = PipelinePromptContext(
            global_llm_system="You are a helpful assistant.",
            recording_llm_instructions="",
            global_whisper_context="",
            recording_whisper_context="",
        )
        self.assertEqual(compose_llm_system_prompt(ctx), "You are a helpful assistant.")

    def test_llm_system_appends_recording(self) -> None:
        ctx = PipelinePromptContext(
            global_llm_system="Base",
            recording_llm_instructions="Extra",
            global_whisper_context="",
            recording_whisper_context="",
        )
        s = compose_llm_system_prompt(ctx)
        self.assertIn("Base", s)
        self.assertIn("Extra", s)

    def test_llm_user_transcript_only(self) -> None:
        self.assertEqual(compose_llm_user_content("hello"), "hello")


if __name__ == "__main__":
    unittest.main()
