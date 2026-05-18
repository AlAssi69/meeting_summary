from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from meeting_assistant.core.constants import (
    DEFAULT_SUMMARY_PROMPT,
    DEFAULT_UI_LANGUAGE,
    DEFAULT_WHISPER_CONTEXT,
    SETTINGS_DEPRECATED_SQLITE_KEYS,
    SETTINGS_KEY_GLOBAL_LLM_SYSTEM,
    SETTINGS_KEY_GLOBAL_WHISPER_CONTEXT,
    SETTINGS_KEY_HF_ACCESS_TOKEN,
    SETTINGS_KEY_MEETING_OUTPUT_ROOT,
    SETTINGS_KEY_UI_LANGUAGE,
    MessageRole,
)
from meeting_assistant.core.models import Message, Session
from meeting_assistant.ports.session_repository import SessionRepository


def _ensure_messages_system_kind_column(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(messages)").fetchall()
    names = {r[1] for r in rows}
    if "system_kind" not in names:
        conn.execute("ALTER TABLE messages ADD COLUMN system_kind TEXT")


def _ensure_message_recording_prompt_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(messages)").fetchall()
    names = {r[1] for r in rows}
    if "recording_llm_instructions" not in names:
        conn.execute("ALTER TABLE messages ADD COLUMN recording_llm_instructions TEXT")
    if "recording_whisper_context" not in names:
        conn.execute("ALTER TABLE messages ADD COLUMN recording_whisper_context TEXT")


def _ensure_assistant_kind_column(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(messages)").fetchall()
    names = {r[1] for r in rows}
    if "assistant_kind" not in names:
        conn.execute("ALTER TABLE messages ADD COLUMN assistant_kind TEXT")


def _ensure_sessions_artifacts_slug_column(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(sessions)").fetchall()
    names = {r[1] for r in rows}
    if "artifacts_slug" not in names:
        conn.execute("ALTER TABLE sessions ADD COLUMN artifacts_slug TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_artifacts_slug "
        "ON sessions(artifacts_slug) WHERE artifacts_slug IS NOT NULL"
    )


def _drop_legacy_sessions_chat_prompt_column(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(sessions)").fetchall()
    names = {r[1] for r in rows}
    if "chat_prompt" not in names:
        return
    try:
        conn.execute("ALTER TABLE sessions DROP COLUMN chat_prompt")
    except sqlite3.OperationalError:
        pass


def _purge_deprecated_app_settings(conn: sqlite3.Connection) -> None:
    if not SETTINGS_DEPRECATED_SQLITE_KEYS:
        return
    keys = tuple(sorted(SETTINGS_DEPRECATED_SQLITE_KEYS))
    placeholders = ",".join("?" * len(keys))
    conn.execute(f"DELETE FROM app_settings WHERE key IN ({placeholders})", keys)


def _ensure_meeting_output_root_setting(conn: sqlite3.Connection) -> None:
    has_key = conn.execute(
        "SELECT 1 FROM app_settings WHERE key = ?", (SETTINGS_KEY_MEETING_OUTPUT_ROOT,)
    ).fetchone()
    if not has_key:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)",
            (SETTINGS_KEY_MEETING_OUTPUT_ROOT, ""),
        )


def _ensure_ui_language_setting(conn: sqlite3.Connection) -> None:
    has_key = conn.execute(
        "SELECT 1 FROM app_settings WHERE key = ?", (SETTINGS_KEY_UI_LANGUAGE,)
    ).fetchone()
    if not has_key:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)",
            (SETTINGS_KEY_UI_LANGUAGE, DEFAULT_UI_LANGUAGE),
        )


def _ensure_hf_access_token_setting(conn: sqlite3.Connection) -> None:
    has_key = conn.execute(
        "SELECT 1 FROM app_settings WHERE key = ?", (SETTINGS_KEY_HF_ACCESS_TOKEN,)
    ).fetchone()
    if not has_key:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)",
            (SETTINGS_KEY_HF_ACCESS_TOKEN, ""),
        )


def _ensure_session_speakers_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_speakers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            speaker_key TEXT NOT NULL,
            speaker_name TEXT NOT NULL,
            UNIQUE(session_id, speaker_key)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_session_speakers_session_id "
        "ON session_speakers(session_id)"
    )


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    artifacts_slug TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT,
    file_path TEXT,
    created_at TEXT NOT NULL,
    system_kind TEXT,
    recording_llm_instructions TEXT,
    recording_whisper_context TEXT,
    assistant_kind TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class SqliteSessionRepository(SessionRepository):
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            _ensure_messages_system_kind_column(conn)
            _ensure_message_recording_prompt_columns(conn)
            _ensure_assistant_kind_column(conn)
            _ensure_sessions_artifacts_slug_column(conn)
            _drop_legacy_sessions_chat_prompt_column(conn)
            _purge_deprecated_app_settings(conn)
            cur_llm = conn.execute(
                "SELECT 1 FROM app_settings WHERE key = ?", (SETTINGS_KEY_GLOBAL_LLM_SYSTEM,)
            )
            if cur_llm.fetchone() is None:
                conn.execute(
                    "INSERT INTO app_settings (key, value) VALUES (?, ?)",
                    (SETTINGS_KEY_GLOBAL_LLM_SYSTEM, DEFAULT_SUMMARY_PROMPT),
                )
            cur_w = conn.execute(
                "SELECT 1 FROM app_settings WHERE key = ?", (SETTINGS_KEY_GLOBAL_WHISPER_CONTEXT,)
            )
            if cur_w.fetchone() is None:
                conn.execute(
                    "INSERT INTO app_settings (key, value) VALUES (?, ?)",
                    (SETTINGS_KEY_GLOBAL_WHISPER_CONTEXT, DEFAULT_WHISPER_CONTEXT),
                )
            _ensure_meeting_output_root_setting(conn)
            _ensure_ui_language_setting(conn)
            _ensure_hf_access_token_setting(conn)
            _ensure_session_speakers_table(conn)
        self._backfill_missing_artifacts_slugs()

    def _backfill_missing_artifacts_slugs(self) -> None:
        from meeting_assistant.services.session_artifact_folder import allocate_unique_session_slug

        while True:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id, title FROM sessions WHERE artifacts_slug IS NULL LIMIT 1"
                ).fetchone()
            if row is None:
                break
            sid = row["id"]
            slug = allocate_unique_session_slug(self, row["title"], exclude_session_id=sid)
            with self._connect() as conn:
                conn.execute(
                    "UPDATE sessions SET artifacts_slug = ? WHERE id = ?",
                    (slug, sid),
                )

    def list_sessions(self) -> list[Session]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, title, created_at, artifacts_slug FROM sessions ORDER BY created_at DESC"
            ).fetchall()
        return [
            Session(
                id=r["id"],
                title=r["title"],
                created_at=r["created_at"],
                artifacts_slug=r["artifacts_slug"],
            )
            for r in rows
        ]

    def create_session(self, title: str) -> Session:
        from meeting_assistant.services.session_artifact_folder import allocate_unique_session_slug

        sid = str(uuid.uuid4())
        created = _iso_now()
        slug = allocate_unique_session_slug(self, title)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, artifacts_slug) VALUES (?, ?, ?, ?)",
                (sid, title, created, slug),
            )
        return Session(id=sid, title=title, created_at=created, artifacts_slug=slug)

    def get_session(self, session_id: str) -> Session | None:
        with self._connect() as conn:
            r = conn.execute(
                "SELECT id, title, created_at, artifacts_slug FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if r is None:
            return None
        return Session(
            id=r["id"],
            title=r["title"],
            created_at=r["created_at"],
            artifacts_slug=r["artifacts_slug"],
        )

    def set_session_title(self, session_id: str, title: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))

    def set_session_artifacts_slug(self, session_id: str, slug: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET artifacts_slug = ? WHERE id = ?",
                (slug, session_id),
            )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str | None,
        file_path: str | None,
        *,
        system_kind: str | None = None,
        recording_llm_instructions: str | None = None,
        recording_whisper_context: str | None = None,
        assistant_kind: str | None = None,
    ) -> Message:
        mid = str(uuid.uuid4())
        created = _iso_now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (id, session_id, role, content, file_path, created_at, "
                "system_kind, recording_llm_instructions, recording_whisper_context, assistant_kind) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    mid,
                    session_id,
                    role,
                    content,
                    file_path,
                    created,
                    system_kind,
                    recording_llm_instructions,
                    recording_whisper_context,
                    assistant_kind,
                ),
            )
        return Message(
            id=mid,
            session_id=session_id,
            role=role,
            content=content,
            file_path=file_path,
            created_at=created,
            system_kind=system_kind,
            recording_llm_instructions=recording_llm_instructions,
            recording_whisper_context=recording_whisper_context,
            assistant_kind=assistant_kind,
        )

    def delete_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def list_messages(self, session_id: str) -> list[Message]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, session_id, role, content, file_path, created_at, system_kind, "
                "recording_llm_instructions, recording_whisper_context, assistant_kind FROM messages "
                "WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        return [
            Message(
                id=r["id"],
                session_id=r["session_id"],
                role=r["role"],
                content=r["content"],
                file_path=r["file_path"],
                created_at=r["created_at"],
                system_kind=r["system_kind"],
                recording_llm_instructions=r["recording_llm_instructions"],
                recording_whisper_context=r["recording_whisper_context"],
                assistant_kind=r["assistant_kind"],
            )
            for r in rows
        ]

    def delete_messages_after_user_with_file(self, session_id: str, file_path: str) -> None:
        try:
            target = str(Path(file_path).resolve())
        except OSError:
            target = file_path
        msgs = self.list_messages(session_id)
        anchor: int | None = None
        for i in range(len(msgs) - 1, -1, -1):
            m = msgs[i]
            if m.role != MessageRole.USER.value or not m.file_path:
                continue
            try:
                if str(Path(m.file_path).resolve()) == target:
                    anchor = i
                    break
            except OSError:
                if m.file_path == file_path:
                    anchor = i
                    break
        if anchor is None:
            return
        to_delete: list[str] = []
        for j in range(anchor + 1, len(msgs)):
            if msgs[j].role == MessageRole.USER.value:
                break
            to_delete.append(msgs[j].id)
        if not to_delete:
            return
        with self._connect() as conn:
            conn.executemany("DELETE FROM messages WHERE id = ?", [(mid,) for mid in to_delete])

    def get_global_llm_system(self) -> str:
        with self._connect() as conn:
            r = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?", (SETTINGS_KEY_GLOBAL_LLM_SYSTEM,)
            ).fetchone()
        return r["value"] if r else DEFAULT_SUMMARY_PROMPT

    def set_global_llm_system(self, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (SETTINGS_KEY_GLOBAL_LLM_SYSTEM, value),
            )

    def get_global_whisper_context(self) -> str:
        with self._connect() as conn:
            r = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?", (SETTINGS_KEY_GLOBAL_WHISPER_CONTEXT,)
            ).fetchone()
        return r["value"] if r else DEFAULT_WHISPER_CONTEXT

    def set_global_whisper_context(self, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (SETTINGS_KEY_GLOBAL_WHISPER_CONTEXT, value),
            )

    def get_meeting_output_root(self) -> str:
        with self._connect() as conn:
            r = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (SETTINGS_KEY_MEETING_OUTPUT_ROOT,),
            ).fetchone()
        return r["value"] if r else ""

    def set_meeting_output_root(self, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (SETTINGS_KEY_MEETING_OUTPUT_ROOT, value.strip()),
            )

    def get_ui_language(self) -> str:
        with self._connect() as conn:
            r = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (SETTINGS_KEY_UI_LANGUAGE,),
            ).fetchone()
        if not r:
            return DEFAULT_UI_LANGUAGE
        v = (r["value"] or "").strip().lower()
        if v in ("ar", "en"):
            return v
        return DEFAULT_UI_LANGUAGE

    def set_ui_language(self, value: str) -> None:
        raw = (value or "").strip().lower()
        if raw not in ("ar", "en"):
            raw = DEFAULT_UI_LANGUAGE
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (SETTINGS_KEY_UI_LANGUAGE, raw),
            )

    def get_hf_access_token(self) -> str:
        with self._connect() as conn:
            r = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (SETTINGS_KEY_HF_ACCESS_TOKEN,),
            ).fetchone()
        return (r["value"] if r else "") or ""

    def set_hf_access_token(self, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (SETTINGS_KEY_HF_ACCESS_TOKEN, value.strip()),
            )

    def list_session_speakers(self, session_id: str) -> list[tuple[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT speaker_key, speaker_name FROM session_speakers "
                "WHERE session_id = ? ORDER BY speaker_key ASC",
                (session_id,),
            ).fetchall()
        return [(str(r["speaker_key"]), str(r["speaker_name"])) for r in rows]

    def replace_session_speakers(self, session_id: str, mapping: dict[str, str]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM session_speakers WHERE session_id = ?", (session_id,))
            for key, name in mapping.items():
                k = (key or "").strip()
                n = (name or "").strip()
                if not k:
                    continue
                if not n:
                    n = k
                conn.execute(
                    "INSERT INTO session_speakers (session_id, speaker_key, speaker_name) "
                    "VALUES (?, ?, ?)",
                    (session_id, k, n),
                )

    def update_assistant_message_content(
        self, session_id: str, message_id: str, content: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE messages SET content = ? WHERE id = ? AND session_id = ? AND role = ?",
                (content, message_id, session_id, MessageRole.ASSISTANT.value),
            )

    def delete_message(self, session_id: str, message_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM messages WHERE id = ? AND session_id = ?",
                (message_id, session_id),
            )
