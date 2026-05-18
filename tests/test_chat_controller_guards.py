"""Guards for staged file vs recording and multi-file drop policy."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from meeting_assistant.adapters.memory_session_repository import InMemorySessionRepository
from meeting_assistant.adapters.mock_summarization import MockSummarizationAdapter
from meeting_assistant.adapters.mock_transcription import MockTranscriptionAdapter
from meeting_assistant.ui.chat_controller import ChatController


def _temp_audio_file(suffix: str = ".wav") -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    p = Path(name)
    p.write_bytes(b"x")
    return p


class TestChatControllerStagingGuards(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_out = tempfile.TemporaryDirectory()
        self.repo = InMemorySessionRepository()
        self.repo.set_meeting_output_root(self._tmp_out.name)
        self.session = self.repo.create_session("guard-test")
        self.chat = ChatController(
            self.repo,
            MockTranscriptionAdapter(),
            MockSummarizationAdapter(),
            transcription_ready=lambda: True,
        )
        self.chat.attach_session_id(self.session.id)

    def tearDown(self) -> None:
        self.chat.deleteLater()
        self._tmp_out.cleanup()

    def test_start_record_blocked_when_pending_and_pending_preserved(self) -> None:
        wav = _temp_audio_file()
        try:
            self.chat.stageAudioFile(str(wav))
            pending = Path(self.chat.pendingAudioPath).resolve()
            self.assertEqual(pending, wav.resolve())

            mock_start = MagicMock()
            self.chat._recording.startRecording = mock_start
            self.chat.startPipelineFromRecorder()
            mock_start.assert_not_called()
            self.assertEqual(Path(self.chat.pendingAudioPath).resolve(), wav.resolve())
            self.assertIn("Send or clear", self.chat.statusText)
        finally:
            wav.unlink(missing_ok=True)

    def test_two_paths_drop_rejected(self) -> None:
        a = _temp_audio_file()
        b = _temp_audio_file()
        try:
            self.chat.stageDroppedLocalPaths([str(a.resolve()), str(b.resolve())])
            self.assertEqual(self.chat.pendingAudioPath, "")
            self.assertIn("one audio file", self.chat.statusText)
        finally:
            a.unlink(missing_ok=True)
            b.unlink(missing_ok=True)

    def test_stage_audio_while_recording_rejected(self) -> None:
        wav = _temp_audio_file()
        try:
            rec = self.chat._recording
            rec._recording = True  # noqa: SLF001 — test seam for recorder active state
            self.chat.stageAudioFile(str(wav))
            self.assertEqual(self.chat.pendingAudioPath, "")
            self.assertIn("Stop recording before importing", self.chat.statusText)
        finally:
            wav.unlink(missing_ok=True)
            self.chat._recording._recording = False  # noqa: SLF001

    def test_discard_pending(self) -> None:
        wav = _temp_audio_file()
        try:
            self.chat.stageAudioFile(str(wav))
            self.assertTrue(len(self.chat.pendingAudioPath) > 0)
            self.chat.discardPendingAudio()
            self.assertEqual(self.chat.pendingAudioPath, "")
            self.assertIn("cleared", self.chat.statusText.lower())
        finally:
            wav.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
