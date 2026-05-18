"""Remove on-disk meeting files when a session is deleted."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from meeting_assistant.ports.session_repository import SessionRepository
from meeting_assistant.services.output_paths import resolve_meeting_output_dirs
from meeting_assistant.services.session_artifact_folder import sessions_root_under_output

_log = logging.getLogger(__name__)


def _is_under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def delete_session_disk_artifacts(repo: SessionRepository, session_id: str) -> None:
    """Delete the session's folder and legacy artifact files referenced by messages."""
    session = repo.get_session(session_id)
    msgs = repo.list_messages(session_id)
    dirs = resolve_meeting_output_dirs(repo)
    root = dirs.root.resolve()

    if session and session.artifacts_slug:
        folder = sessions_root_under_output(root) / session.artifacts_slug
        if folder.is_dir():
            try:
                shutil.rmtree(folder)
            except OSError as e:
                _log.warning("Could not remove session folder %s: %s", folder, e)
                raise

    seen: set[str] = set()
    for m in msgs:
        fp = (m.file_path or "").strip()
        if not fp or fp in seen:
            continue
        seen.add(fp)
        p = Path(fp)
        if not p.is_file():
            continue
        try:
            rp = p.resolve()
        except OSError:
            continue
        if not _is_under_root(rp, root):
            continue
        try:
            rp.unlink()
        except OSError as e:
            _log.warning("Could not remove artifact file %s: %s", rp, e)
