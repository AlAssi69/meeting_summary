"""Speaker diarization enabled flag: resolver and repository."""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from meeting_assistant.adapters.memory_session_repository import InMemorySessionRepository
from meeting_assistant.adapters.sqlite_session_repository import SqliteSessionRepository
from meeting_assistant.services.hf_token import resolve_speaker_diarization_enabled
from meeting_assistant.services.whisperx_engine import WhisperXEngine


class TestDiarizationSettings(unittest.TestCase):
    def test_memory_repo_default_on(self) -> None:
        repo = InMemorySessionRepository()
        self.assertTrue(repo.get_speaker_diarization_enabled())

    def test_memory_repo_round_trip(self) -> None:
        repo = InMemorySessionRepository()
        repo.set_speaker_diarization_enabled(False)
        self.assertFalse(repo.get_speaker_diarization_enabled())
        repo.set_speaker_diarization_enabled(True)
        self.assertTrue(repo.get_speaker_diarization_enabled())

    def test_sqlite_default_on_fresh_db(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "t.db"
            repo = SqliteSessionRepository(db)
            self.assertTrue(repo.get_speaker_diarization_enabled())
            del repo
            gc.collect()

    def test_sqlite_round_trip(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "t.db"
            repo = SqliteSessionRepository(db)
            repo.set_speaker_diarization_enabled(False)
            self.assertFalse(repo.get_speaker_diarization_enabled())
            del repo
            gc.collect()
            repo2 = SqliteSessionRepository(db)
            self.assertFalse(repo2.get_speaker_diarization_enabled())
            del repo2
            gc.collect()

    def test_resolve_prefers_repo(self) -> None:
        repo = InMemorySessionRepository()
        repo.set_speaker_diarization_enabled(False)
        with patch("meeting_assistant.services.hf_token.config.SPEAKER_DIARIZATION_ENABLED", True):
            self.assertFalse(resolve_speaker_diarization_enabled(repo))

    def test_resolve_falls_back_to_config(self) -> None:
        with patch("meeting_assistant.services.hf_token.config.SPEAKER_DIARIZATION_ENABLED", False):
            self.assertFalse(resolve_speaker_diarization_enabled(None))


class TestWhisperXEngineDiarizationGate(unittest.TestCase):
    def test_hf_required_when_diarization_on(self) -> None:
        engine = WhisperXEngine(token_resolver=lambda: "", diarization_resolver=lambda: True)
        with self.assertRaises(RuntimeError):
            engine.transcribe(Path("x.wav"))
        self.assertEqual(engine.last_failure_kind, "hf_auth")

    def test_hf_not_required_when_diarization_off(self) -> None:
        engine = WhisperXEngine(token_resolver=lambda: "", diarization_resolver=lambda: False)
        captured: dict = {}

        def fake_locked(*_a, **kw):
            captured["diarization_on"] = kw.get("diarization_on")
            return "aligned text"

        engine._transcribe_locked = fake_locked  # type: ignore[method-assign]
        out = engine.transcribe(Path("x.wav"))
        self.assertEqual(out, "aligned text")
        self.assertFalse(captured["diarization_on"])
        self.assertEqual(engine.last_failure_kind, "")


if __name__ == "__main__":
    unittest.main()
