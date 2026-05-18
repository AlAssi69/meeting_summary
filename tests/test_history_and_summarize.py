"""Tests for transcript/summary history, assistant_kind, and anchor helpers."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from meeting_assistant.adapters.memory_session_repository import InMemorySessionRepository
from meeting_assistant.adapters.sqlite_session_repository import SqliteSessionRepository
from meeting_assistant.core.constants import AssistantContentKind, MessageRole
from meeting_assistant.core.models import Message
from meeting_assistant.ui.chat_controller import (
    _find_anchor_user_before_index,
    _is_transcript_message,
)


class TestAnchorHelpers(unittest.TestCase):
    def test_find_anchor_user_before_transcript(self) -> None:
        u = Message(
            id="u1",
            session_id="s",
            role=MessageRole.USER.value,
            content="Audio: x",
            file_path="/path/rec.wav",
            created_at="2026-01-01T00:00:00Z",
            recording_llm_instructions="focus sales",
            recording_whisper_context="names",
        )
        t = Message(
            id="t1",
            session_id="s",
            role=MessageRole.ASSISTANT.value,
            content="hello text",
            file_path="/path/tr.txt",
            created_at="2026-01-01T00:01:00Z",
            assistant_kind=AssistantContentKind.TRANSCRIPT.value,
        )
        msgs = [u, t]
        a = _find_anchor_user_before_index(msgs, 1)
        self.assertIsNotNone(a)
        assert a is not None
        self.assertEqual(a.recording_llm_instructions, "focus sales")
        self.assertEqual(a.recording_whisper_context, "names")

    def test_is_transcript_explicit_and_legacy(self) -> None:
        tr = Message(
            id="a",
            session_id="s",
            role=MessageRole.ASSISTANT.value,
            content="x",
            file_path="/t.txt",
            created_at="t",
            assistant_kind=AssistantContentKind.TRANSCRIPT.value,
        )
        self.assertTrue(_is_transcript_message(tr))
        sm = Message(
            id="b",
            session_id="s",
            role=MessageRole.ASSISTANT.value,
            content="y",
            file_path=None,
            created_at="t",
            assistant_kind=AssistantContentKind.SUMMARY.value,
        )
        self.assertFalse(_is_transcript_message(sm))
        legacy = Message(
            id="c",
            session_id="s",
            role=MessageRole.ASSISTANT.value,
            content="z",
            file_path="/old.txt",
            created_at="t",
            assistant_kind=None,
        )
        self.assertTrue(_is_transcript_message(legacy))


class TestSqliteAssistantKind(unittest.TestCase):
    def test_round_trip_assistant_kind(self) -> None:
        repo = InMemorySessionRepository()
        with tempfile.TemporaryDirectory() as td:
            repo.set_meeting_output_root(td)
            s = repo.create_session("test")
            repo.add_message(
                s.id,
                MessageRole.ASSISTANT.value,
                "body",
                "/x.txt",
                assistant_kind=AssistantContentKind.TRANSCRIPT.value,
            )
            msgs = repo.list_messages(s.id)
            self.assertEqual(len(msgs), 1)
            self.assertEqual(msgs[0].assistant_kind, AssistantContentKind.TRANSCRIPT.value)

    def test_sqlite_new_db_has_assistant_kind_column(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        try:
            SqliteSessionRepository(path)
            sqlite3 = __import__("sqlite3")
            conn = sqlite3.connect(path)
            names = {r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()}
            conn.close()
            self.assertIn("assistant_kind", names)
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def test_sqlite_startup_purges_deprecated_settings_and_drops_chat_prompt(self) -> None:
        sqlite3 = __import__("sqlite3")
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        try:
            conn = sqlite3.connect(path)
            conn.executescript(
                """
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    chat_prompt TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    file_path TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );
                CREATE TABLE app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?)",
                ("global_default_prompt", "old"),
            )
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?)",
                ("prompt_bundle_v2_applied", "1"),
            )
            conn.commit()
            conn.close()

            SqliteSessionRepository(path)

            conn2 = sqlite3.connect(path)
            keys = {
                r[0]
                for r in conn2.execute("SELECT key FROM app_settings").fetchall()
            }
            self.assertNotIn("global_default_prompt", keys)
            self.assertNotIn("prompt_bundle_v2_applied", keys)
            names = {r[1] for r in conn2.execute("PRAGMA table_info(sessions)").fetchall()}
            conn2.close()
            if sqlite3.sqlite_version_info < (3, 35, 0):
                self.skipTest("SQLite < 3.35 has no ALTER TABLE DROP COLUMN")
            self.assertNotIn("chat_prompt", names)
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def test_sqlite_round_trip_assistant_kind(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        try:
            repo = SqliteSessionRepository(path)
            root = Path(tempfile.mkdtemp())
            try:
                repo.set_meeting_output_root(str(root))
                s = repo.create_session("sqlite")
                repo.add_message(
                    s.id,
                    MessageRole.ASSISTANT.value,
                    "t",
                    None,
                    assistant_kind=AssistantContentKind.SUMMARY.value,
                )
                msgs = repo.list_messages(s.id)
                self.assertEqual(msgs[0].assistant_kind, AssistantContentKind.SUMMARY.value)
            finally:
                shutil.rmtree(root, ignore_errors=True)
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
