from __future__ import annotations

from meeting_assistant.services.prompt_composition import PipelinePromptContext


def run_prompt_context(*, llm_instructions: str, whisper_context: str) -> PipelinePromptContext:
    """Build prompt context for one pipeline/summarize run from user-entered strings only.

    Global layers are left empty; instructions live in the recording slots so existing
    composition helpers behave as a single effective prompt per model.
    """
    return PipelinePromptContext(
        global_llm_system="",
        recording_llm_instructions=(llm_instructions or "").strip(),
        global_whisper_context="",
        recording_whisper_context=(whisper_context or "").strip(),
    )
