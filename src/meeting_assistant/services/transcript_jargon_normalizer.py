"""Optional Ollama pass: fix Arabized English technical terms while preserving diarized layout."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from meeting_assistant import config
from meeting_assistant.services.prompt_composition import (
    PipelinePromptContext,
    compose_whisper_initial_prompt,
)

_log = logging.getLogger(__name__)

_JARGON_SYSTEM = (
    "You are a technical transcript editor. The transcript may mix Arabic with English technical terms. "
    "Some English words may have been written with Arabic letters; when you are confident they match a "
    "term implied by the glossary, replace that Arabic-letter spelling with the correct Latin spelling "
    "from the glossary (or standard industry spelling). Do not change correct Arabic text. "
    "Do not add commentary, headings, or markdown. "
    "Preserve structure exactly: same number of lines, same order. "
    "For each line that begins with a speaker label and timestamp (format like "
    "'SPEAKER_00 [00:12 - 00:18]: '), the part before the first '] ' must stay character-identical "
    "to the input line — only edit the text after that prefix. "
    "Output only the transcript lines, nothing else."
)


def _is_probably_diarized(text: str) -> bool:
    return "SPEAKER_" in text and "]: " in text


# One line from format_diarized_transcript: SPEAKER_00 [MM:SS - MM:SS]: body
_DIARIZED_PREFIX_RE = re.compile(r"^([A-Z0-9_]+\s+\[[^\]]+\]:\s)")


def _prefix_through_first_bracket_colon(line: str) -> str | None:
    m = _DIARIZED_PREFIX_RE.match(line)
    return m.group(1) if m else None


def _structure_preserved(original: str, edited: str) -> bool:
    o_lines = original.splitlines()
    e_lines = edited.splitlines()
    if len(o_lines) != len(e_lines):
        return False
    if not _is_probably_diarized(original):
        return True
    for o, e in zip(o_lines, e_lines):
        po, pe = _prefix_through_first_bracket_colon(o), _prefix_through_first_bracket_colon(e)
        if po is None or pe is None:
            if o != e:
                return False
            continue
        if po != pe:
            return False
    return True


def _ollama_chat(system: str, user: str) -> str:
    url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    body: dict[str, Any] = {
        "model": config.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    with httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
        r = client.post(url, json=body)
        r.raise_for_status()
        data = r.json()
    msg = data.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(data.get("response"), str):
        return str(data["response"]).strip()
    raise RuntimeError(f"Unexpected Ollama response: {data!r}")


def normalize_transcript_with_glossary(transcript: str, glossary: str) -> str:
    """Call Ollama to normalize jargon. Raises on HTTP/contract errors; caller may fall back."""
    user = (
        "Glossary / transcription bias text (English terms to prefer in Latin letters):\n\n"
        f"{glossary}\n\n---\n\nTranscript:\n\n{transcript}"
    )
    out = _ollama_chat(_JARGON_SYSTEM, user)
    if not _structure_preserved(transcript, out):
        raise RuntimeError("Jargon normalizer output failed structure validation")
    return out


def maybe_normalize_transcript(transcript: str, prompt_context: PipelinePromptContext) -> str:
    """When enabled, run jargon normalization using composed Whisper context as glossary."""
    if config.USE_MOCK_BACKEND or not config.TRANSCRIPT_JARGON_NORMALIZE:
        return transcript
    t = transcript.strip()
    if not t or t == "(No speech detected)":
        return transcript
    glossary = compose_whisper_initial_prompt(prompt_context) or ""
    if not glossary.strip():
        return transcript
    try:
        out = normalize_transcript_with_glossary(transcript, glossary.strip())
        _log.info("Transcript jargon normalization applied (%d -> %d chars)", len(transcript), len(out))
        return out
    except Exception as e:
        _log.warning("Transcript jargon normalization skipped: %s", e)
        return transcript
