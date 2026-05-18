"""Per-session folders under ``<output_root>/sessions/<slug>/``.

Folders are created when a session first needs on-disk artifacts (recording or pipeline),
not when the session row is inserted — see :func:`ensure_repo_session_has_slug`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from meeting_assistant.core.models import Session
from meeting_assistant.ports.session_repository import SessionRepository
from meeting_assistant.services.output_paths import MeetingOutputDirs, resolve_meeting_output_dirs
from meeting_assistant.services.transcript_file import sanitize_title_for_filename

_log = logging.getLogger(__name__)


def sessions_root_under_output(output_root: Path) -> Path:
    return output_root / "sessions"


def reserved_session_folder_names(
    repo: SessionRepository,
    *,
    exclude_session_id: str | None = None,
    exclude_dir_name: str | None = None,
) -> set[str]:
    names: set[str] = set()
    for s in repo.list_sessions():
        if exclude_session_id and s.id == exclude_session_id:
            continue
        if s.artifacts_slug:
            names.add(s.artifacts_slug)
    root = resolve_meeting_output_dirs(repo).root
    sr = sessions_root_under_output(root)
    if sr.is_dir():
        for p in sr.iterdir():
            if not p.is_dir():
                continue
            if exclude_dir_name and p.name == exclude_dir_name:
                continue
            names.add(p.name)
    return names


def allocate_unique_session_slug(
    repo: SessionRepository,
    title: str,
    *,
    exclude_session_id: str | None = None,
    exclude_dir_name: str | None = None,
) -> str:
    taken = reserved_session_folder_names(
        repo, exclude_session_id=exclude_session_id, exclude_dir_name=exclude_dir_name
    )
    base = sanitize_title_for_filename((title or "").strip() or "Meeting")
    stem = base
    n = 2
    while stem in taken:
        stem = f"{base}_{n}"
        n += 1
    return stem


def ensure_session_folder_exists(repo: SessionRepository, slug: str) -> Path:
    root = resolve_meeting_output_dirs(repo).root
    path = sessions_root_under_output(root) / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def prune_empty_session_artifact_folders(repo: SessionRepository) -> int:
    """Remove empty subdirectories under ``sessions/`` (orphans or never-used session folders).

    Safe for active sessions that have no files yet: the folder is recreated on the next
    recording or pipeline run via :func:`ensure_repo_session_has_slug`.
    """
    root = resolve_meeting_output_dirs(repo).root
    sr = sessions_root_under_output(root)
    if not sr.is_dir():
        return 0
    removed = 0
    for p in sorted(sr.iterdir(), key=lambda x: x.name, reverse=True):
        if not p.is_dir():
            continue
        try:
            if any(p.iterdir()):
                continue
            p.rmdir()
            removed += 1
        except OSError:
            continue
    return removed


def resolve_session_meeting_dirs(repo: SessionRepository, session: Session) -> MeetingOutputDirs:
    if not session.artifacts_slug:
        raise ValueError("session missing artifacts_slug")
    root_dirs = resolve_meeting_output_dirs(repo)
    folder = sessions_root_under_output(root_dirs.root) / session.artifacts_slug
    return MeetingOutputDirs(
        root=root_dirs.root,
        recordings=folder,
        transcripts=folder,
        summaries=folder,
    )


def ensure_repo_session_has_slug(repo: SessionRepository, session_id: str) -> Session:
    s = repo.get_session(session_id)
    if s is None:
        raise KeyError(session_id)
    if s.artifacts_slug:
        return s
    slug = allocate_unique_session_slug(repo, s.title, exclude_session_id=session_id)
    ensure_session_folder_exists(repo, slug)
    repo.set_session_artifacts_slug(session_id, slug)
    out = repo.get_session(session_id)
    if out is None or not out.artifacts_slug:
        raise RuntimeError("failed to persist session artifacts slug")
    return out


def rename_session_folder_on_disk(
    repo: SessionRepository,
    *,
    old_slug: str | None,
    new_slug: str,
) -> None:
    root = resolve_meeting_output_dirs(repo).root
    sessions_root = sessions_root_under_output(root)
    sessions_root.mkdir(parents=True, exist_ok=True)
    dest = sessions_root / new_slug
    if old_slug == new_slug:
        dest.mkdir(parents=True, exist_ok=True)
        return
    if old_slug:
        src = sessions_root / old_slug
        if src.is_dir():
            if dest.exists():
                raise OSError(f"Target session folder already exists: {dest}")
            src.rename(dest)
            return
    dest.mkdir(parents=True, exist_ok=True)


def try_rename_session_artifacts_folder(
    repo: SessionRepository,
    *,
    old_slug: str | None,
    new_slug: str,
) -> tuple[bool, str]:
    try:
        rename_session_folder_on_disk(repo, old_slug=old_slug, new_slug=new_slug)
        return True, ""
    except OSError as e:
        _log.warning("Session folder rename failed: %s", e)
        return False, str(e)
