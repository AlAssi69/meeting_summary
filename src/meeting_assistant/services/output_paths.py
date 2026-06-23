"""Resolve where meeting recordings, transcripts, and summaries are stored."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from meeting_assistant import config
from meeting_assistant.ports.session_repository import SessionRepository


@dataclass(frozen=True)
class MeetingOutputDirs:
    root: Path
    recordings: Path
    transcripts: Path
    summaries: Path


def resolve_meeting_output_dirs(repo: SessionRepository) -> MeetingOutputDirs:
    """Pick root: MEETING_ASSISTANT_OUTPUT_ROOT > repo setting > project default.

    ``MEETING_ASSISTANT_OUTPUT_ROOT`` is documented in README.md (env tables) and
    ``.env.example``; it is read here, not in ``config.py``.
    """
    env_root = os.environ.get("MEETING_ASSISTANT_OUTPUT_ROOT", "").strip()
    if env_root:
        root = Path(env_root).expanduser().resolve()
    else:
        custom = repo.get_meeting_output_root().strip()
        if custom:
            root = Path(custom).expanduser().resolve()
        else:
            root = config.DEFAULT_MEETING_OUTPUT_ROOT.resolve()

    transcripts_dir = root / "transcripts"

    return MeetingOutputDirs(
        root=root,
        recordings=root / "recordings",
        transcripts=transcripts_dir,
        summaries=root / "summaries",
    )


def ensure_output_dirs(dirs: MeetingOutputDirs) -> None:
    dirs.recordings.mkdir(parents=True, exist_ok=True)
    dirs.transcripts.mkdir(parents=True, exist_ok=True)
    dirs.summaries.mkdir(parents=True, exist_ok=True)
