"""Resolve Hugging Face token for pyannote / WhisperX diarization."""

from __future__ import annotations

from meeting_assistant import config
from meeting_assistant.ports.session_repository import SessionRepository


def resolve_hf_access_token(repo: SessionRepository | None = None) -> str:
    """Prefer persisted settings; otherwise environment (see ``config.HF_ACCESS_TOKEN``)."""
    if repo is not None:
        try:
            t = (repo.get_hf_access_token() or "").strip()
            if t:
                return t
        except Exception:
            pass
    return (config.HF_ACCESS_TOKEN or "").strip()
