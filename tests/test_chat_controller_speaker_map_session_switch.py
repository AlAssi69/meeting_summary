"""Speaker-map pending on session A must not block staging on B; pipeline start stays global."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from meeting_assistant.adapters.memory_session_repository import InMemorySessionRepository
from meeting_assistant.adapters.mock_summarization import MockSummarizationAdapter
from meeting_assistant.adapters.mock_transcription import MockTranscriptionAdapter
from meeting_assistant.ui.chat_controller import ChatController


def _temp_file(suffix: str, content: bytes = b"x") -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    p = Path(name)
    p.write_bytes(content)
    return p


class TestChatControllerSpeakerMapSessionSwitch(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_out = tempfile.TemporaryDirectory()
        self.repo = InMemorySessionRepository()
        self.repo.set_meeting_output_root(self._tmp_out.name)
        self.session_a = self.repo.create_session("session-a")
        self.session_b = self.repo.create_session("session-b")
        self.chat = ChatController(
            self.repo,
            MockTranscriptionAdapter(),
            MockSummarizationAdapter(),
            transcription_ready=lambda: True,
        )

    def tearDown(self) -> None:
        self.chat.deleteLater()
        self._tmp_out.cleanup()

    def test_other_session_can_stage_while_speaker_map_pending(self) -> None:
        chat = self.chat
        chat.attach_session_id(self.session_a.id)
        txt = _temp_file(".txt", b"SPEAKER_00: hi\n")
        try:
            chat._pipeline_session_id = self.session_a.id  # noqa: SLF001
            chat._on_transcription_finished_raw("SPEAKER_00: hi\n", str(txt), ["SPEAKER_00"])  # noqa: SLF001
            self.assertTrue(chat.pipelineStartLocked)
            self.assertEqual(chat.currentPhase, "awaiting_speaker_map")

            chat.attach_session_id(self.session_b.id)
            self.assertFalse(chat.stagingImportLocked)

            wav = _temp_file(".wav")
            try:
                chat.stageAudioFile(str(wav))
                self.assertTrue(len(chat.pendingAudioPath) > 0)
                chat.sendPendingAudio()
                self.assertIn(
                    "another session",
                    chat.statusText.lower(),
                    msg=chat.statusText,
                )
            finally:
                wav.unlink(missing_ok=True)
        finally:
            txt.unlink(missing_ok=True)
