"""Compose Whisper initial_prompt and LLM messages from global and per-recording layers.

Whisper (faster-whisper) accepts a single ``initial_prompt`` string. When trimming, we keep
the **suffix** so **per-recording transcription context** is favored over **global**
(low-priority text is at the start and drops first under length limits).
"""

from __future__ import annotations

from dataclasses import dataclass

# Practical cap for initial_prompt token budget (rough char guard).
WHISPER_INITIAL_PROMPT_MAX_CHARS: int = 1800

_LLM_RECORDING_SEP: str = "\n\n--- Recording summarization instructions ---\n\n"
_WHISPER_BLOCK_SEP: str = "\n\n---\n\n"


@dataclass(frozen=True)
class PipelinePromptContext:
    """Snapshot of all prompt inputs for one pipeline run (GUI thread)."""

    global_llm_system: str
    recording_llm_instructions: str
    global_whisper_context: str
    recording_whisper_context: str


def _strip(s: str) -> str:
    return (s or "").strip()


def compose_whisper_initial_prompt(ctx: PipelinePromptContext) -> str | None:
    """Return ``initial_prompt`` for faster-whisper, or ``None`` if nothing to pass."""
    g = _strip(ctx.global_whisper_context)
    r = _strip(ctx.recording_whisper_context)
    if not (g or r):
        return None
    # Global first (lower priority); suffix retention favors per-recording context.
    parts: list[str] = []
    if g:
        parts.append(g)
    if r:
        parts.append(r)
    joined = _WHISPER_BLOCK_SEP.join(parts)
    if len(joined) <= WHISPER_INITIAL_PROMPT_MAX_CHARS:
        return joined
    return joined[-WHISPER_INITIAL_PROMPT_MAX_CHARS:].lstrip()


def compose_llm_system_prompt(ctx: PipelinePromptContext) -> str:
    """LLM system message: global system + optional per-recording summarization instructions."""
    base = _strip(ctx.global_llm_system)
    rec = _strip(ctx.recording_llm_instructions)
    if not rec:
        return base or "Summarize the following."
    if not base:
        return rec
    return base + _LLM_RECORDING_SEP + rec


def compose_llm_user_content(transcript: str) -> str:
    """LLM user message: transcript only (per-recording instructions live in system)."""
    return _strip(transcript)
