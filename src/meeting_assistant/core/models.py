"""Light domain models (no framework deps)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Session:
    id: str
    title: str
    created_at: str
    artifacts_slug: str | None = None


@dataclass(frozen=True)
class Message:
    id: str
    session_id: str
    role: str
    content: str | None
    file_path: str | None
    created_at: str
    system_kind: str | None = field(default=None)
    recording_llm_instructions: str | None = field(default=None)
    recording_whisper_context: str | None = field(default=None)
    assistant_kind: str | None = field(default=None)
