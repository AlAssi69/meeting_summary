"""SQLite HF token and session_speakers persistence."""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path

from meeting_assistant.adapters.sqlite_session_repository import SqliteSessionRepository
from meeting_assistant.services.hf_token import resolve_hf_access_token


class TestSqliteHfAndSpeakers(unittest.TestCase):
    def test_hf_token_round_trip(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "t.db"
            repo = SqliteSessionRepository(db)
            self.assertEqual(repo.get_hf_access_token(), "")
            repo.set_hf_access_token("hf_testtoken123")
            self.assertEqual(repo.get_hf_access_token(), "hf_testtoken123")
            del repo
            gc.collect()
            repo2 = SqliteSessionRepository(db)
            self.assertEqual(repo2.get_hf_access_token(), "hf_testtoken123")
            del repo2
            gc.collect()

    def test_resolve_hf_prefers_db_over_env(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "t.db"
            repo = SqliteSessionRepository(db)
            repo.set_hf_access_token("hf_from_db")
            self.assertEqual(resolve_hf_access_token(repo), "hf_from_db")
            del repo
            gc.collect()

    def test_session_speakers_replace_and_delete_session_cascade(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "t.db"
            repo = SqliteSessionRepository(db)
            s = repo.create_session("meet")
            repo.replace_session_speakers(s.id, {"SPEAKER_00": "A", "SPEAKER_01": "B"})
            rows = dict(repo.list_session_speakers(s.id))
            self.assertEqual(rows["SPEAKER_00"], "A")
            self.assertEqual(rows["SPEAKER_01"], "B")
            repo.replace_session_speakers(s.id, {"SPEAKER_00": "Ann"})
            rows2 = dict(repo.list_session_speakers(s.id))
            self.assertEqual(rows2, {"SPEAKER_00": "Ann"})
            repo.delete_session(s.id)
            self.assertEqual(repo.list_session_speakers(s.id), [])
            del repo
            gc.collect()


if __name__ == "__main__":
    unittest.main()
