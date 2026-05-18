#!/usr/bin/env python3
"""Read-only SQLite check for sensitive app_settings (redacted output).

Usage:
  python scripts/audit_sqlite_privacy.py [path/to/meetings.db]

If no path is given, resolves the DB the same way as the app (see ``meeting_assistant.config``):
``MEETING_ASSISTANT_DB`` if set and the file exists; else ``{DATA_DIR}/meetings.db`` where
``DATA_DIR`` is ``MEETING_ASSISTANT_DATA_DIR`` or the OS default (e.g. Windows
``%LOCALAPPDATA%\\MeetingAssistant``); else ``./meetings.db`` under the repo root.
Does not print secret values — only key names, non-empty flags, and value lengths.
Flags (counts only) when stored paths appear to live under the repository root — a risk
if the database is copied into the tree or published.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_SENSITIVE_KEYS = (
    "hf_access_token",
    "meeting_output_root",
    "ui_language",
    "global_llm_system",
    "global_whisper_context",
)

_SETTINGS_KEY_MEETING_OUTPUT_ROOT = "meeting_output_root"


def _default_data_dir() -> Path:
    """Mirror ``config.DATA_DIR`` when ``MEETING_ASSISTANT_DATA_DIR`` is unset."""
    override = (os.environ.get("MEETING_ASSISTANT_DATA_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "MeetingAssistant"
    return Path.home() / ".local" / "share" / "MeetingAssistant"


def _resolve_db_path(argv: list[str]) -> Path | None:
    if len(argv) > 1:
        p = Path(argv[1]).expanduser()
        return p if p.is_file() else None
    env_db = (os.environ.get("MEETING_ASSISTANT_DB") or "").strip()
    if env_db:
        pe = Path(env_db).expanduser()
        if pe.is_file():
            return pe
    default_db = _default_data_dir() / "meetings.db"
    if default_db.is_file():
        return default_db
    cand = REPO_ROOT / "meetings.db"
    if cand.is_file():
        return cand
    return None


def _resolved_path_for_repo_audit(raw: str) -> Path | None:
    t = (raw or "").strip()
    if not t:
        return None
    p = Path(t)
    try:
        if p.is_absolute():
            return p.resolve()
        return (REPO_ROOT / p).resolve()
    except OSError:
        return None


def _path_under_repo(path: Path, repo_resolved: Path) -> bool:
    try:
        path.relative_to(repo_resolved)
        return True
    except ValueError:
        return False


def _audit_paths_under_repo(cur: sqlite3.Cursor, repo_resolved: Path) -> None:
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='app_settings'"
    )
    if cur.fetchone():
        cur.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (_SETTINGS_KEY_MEETING_OUTPUT_ROOT,),
        )
        row = cur.fetchone()
        root_val = (row[0] or "").strip() if row else ""
        if root_val:
            rp = _resolved_path_for_repo_audit(root_val)
            if rp is not None and _path_under_repo(rp, repo_resolved):
                print(
                    "  meeting_output_root: resolves inside repo clone "
                    "(risk if DB is committed or shared; path not printed)."
                )

    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='messages'"
    )
    if cur.fetchone() is None:
        return

    cur.execute(
        """
        SELECT file_path FROM messages
        WHERE file_path IS NOT NULL AND TRIM(file_path) != ''
        """
    )
    under = 0
    total = 0
    for (fp,) in cur.fetchall():
        total += 1
        rp = _resolved_path_for_repo_audit(fp)
        if rp is not None and _path_under_repo(rp, repo_resolved):
            under += 1

    if total:
        print(f"  messages with non-empty file_path: {total}")
        if under:
            print(
                f"  messages with file_path under repo clone: {under} "
                "(audio/transcript paths; do not commit this DB if unintended)."
            )
        else:
            print("  messages with file_path under repo clone: 0")


def main() -> int:
    db_path = _resolve_db_path(sys.argv)
    if db_path is None:
        hint = _default_data_dir() / "meetings.db"
        print("audit_sqlite_privacy: no database file found (nothing to scan).")
        print("  Pass a path: python scripts/audit_sqlite_privacy.py path/to/meetings.db")
        print(
            "  Or use the app defaults: set MEETING_ASSISTANT_DB / MEETING_ASSISTANT_DATA_DIR, "
            "place meetings.db in the repo root, or ensure the file exists at:"
        )
        print(f"    {hint}")
        return 0

    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as e:
        print(f"audit_sqlite_privacy: could not open read-only: {e}")
        return 1

    try:
        cur = conn.cursor()
        print(f"audit_sqlite_privacy: {db_path} (read-only)")

        cur.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='app_settings'
            """
        )
        if cur.fetchone() is None:
            print("  no app_settings table (skip settings scan).")
        else:
            cur.execute(
                """
                SELECT key, length(COALESCE(value, '')) AS len
                FROM app_settings
                WHERE key IN ({})
                   OR key LIKE '%token%'
                   OR key LIKE '%secret%'
                """.format(",".join("?" * len(_SENSITIVE_KEYS))),
                _SENSITIVE_KEYS,
            )
            rows = cur.fetchall()
            if not rows:
                print("  (no matching app_settings rows)")
            else:
                for key, length in sorted(rows, key=lambda x: x[0]):
                    flag = "set" if length else "empty"
                    extra = ""
                    if key == "hf_access_token" and length:
                        extra = (
                            " - rotate on Hugging Face if this file was ever "
                            "committed or shared"
                        )
                    print(f"  {key}: {flag} (value length={length}){extra}")

        cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sessions'"
        )
        if cur.fetchone():
            cur.execute("SELECT COUNT(*) FROM sessions")
            (n_sessions,) = cur.fetchone()
            print(f"  sessions count: {n_sessions}")
        else:
            print("  no sessions table.")

        _audit_paths_under_repo(cur, REPO_ROOT.resolve())
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
