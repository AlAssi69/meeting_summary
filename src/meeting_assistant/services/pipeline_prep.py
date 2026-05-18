"""Shared setup for transcription / pipeline runs (DRY between ChatController and workers)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from meeting_assistant.ports.session_repository import SessionRepository
from meeting_assistant.services.output_paths import MeetingOutputDirs
from meeting_assistant.services.prompt_composition import PipelinePromptContext
from meeting_assistant.services.session_artifact_folder import (
    ensure_repo_session_has_slug,
    resolve_session_meeting_dirs,
)
from meeting_assistant.services.transcript_file import (
    build_meeting_artifact_stem,
    rename_temp_recording_if_needed,
    resolve_unique_pipeline_stem_in_dir,
)


@dataclass(frozen=True)
class PipelinePrep:
    session_id: str
    working_audio: Path
    artifact_stem: str
    prompt_context: PipelinePromptContext
    output_dirs: MeetingOutputDirs


def prepare_pipeline_audio_and_stem(
    repo: SessionRepository,
    session_id: str,
    audio_path: Path,
    *,
    prompt_context: PipelinePromptContext,
) -> PipelinePrep:
    session = ensure_repo_session_has_slug(repo, session_id)
    out_dirs = resolve_session_meeting_dirs(repo, session)
    out_dirs.recordings.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    base_stem = build_meeting_artifact_stem(session.title, session_id, now=now)
    artifact_stem = resolve_unique_pipeline_stem_in_dir(base_stem, out_dirs.recordings)
    working_audio = rename_temp_recording_if_needed(
        audio_path, out_dirs.recordings, artifact_stem
    )
    try:
        w_res = working_audio.resolve()
        d_res = out_dirs.recordings.resolve()
    except OSError:
        w_res, d_res = working_audio, out_dirs.recordings
    if w_res.parent != d_res:
        dest = out_dirs.recordings / f"{artifact_stem}{working_audio.suffix}"
        shutil.copy2(working_audio, dest)
        working_audio = dest
    resolved = working_audio.resolve()
    return PipelinePrep(
        session_id=session_id,
        working_audio=resolved,
        artifact_stem=artifact_stem,
        prompt_context=prompt_context,
        output_dirs=out_dirs,
    )
