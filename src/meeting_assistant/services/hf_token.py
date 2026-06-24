"""Resolve Hugging Face token and speaker diarization flag for WhisperX."""

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


def resolve_speaker_diarization_enabled(repo: SessionRepository | None = None) -> bool:
    """Prefer persisted settings; otherwise ``config.SPEAKER_DIARIZATION_ENABLED``."""
    if repo is not None:
        try:
            return bool(repo.get_speaker_diarization_enabled())
        except Exception:
            pass
    return bool(config.SPEAKER_DIARIZATION_ENABLED)
