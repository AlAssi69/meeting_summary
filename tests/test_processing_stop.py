"""Stop processing and cooperative cancellation (mock backend)."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QTimer

from meeting_assistant import config
from meeting_assistant.adapters.memory_session_repository import InMemorySessionRepository
from meeting_assistant.adapters.mock_summarization import MockSummarizationAdapter
from meeting_assistant.adapters.mock_transcription import MockTranscriptionAdapter
from meeting_assistant.core.constants import AssistantContentKind, MessageRole, MessageSystemKind
from meeting_assistant.ui.chat_controller import ChatController


class TestProcessingStop(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if QCoreApplication.instance() is None:
            QCoreApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "chat"):
            self.chat.deleteLater()
            app = QCoreApplication.instance()
            if app is not None:
                app.processEvents()

    def _pump(self, max_sec: float = 12.0) -> None:
        app = QCoreApplication.instance()
        assert app is not None
        deadline = time.monotonic() + max_sec
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.02)

    def test_stop_during_first_mock_delay_no_transcript_row(self) -> None:
        repo = InMemorySessionRepository()
        tmp_out = tempfile.TemporaryDirectory()
        repo.set_meeting_output_root(tmp_out.name)
        try:
            session = repo.create_session("stop-early")
            wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            wav.write(b"x")
            wav.close()
            p = Path(wav.name)
            try:
                with patch.object(config, "USE_MOCK_BACKEND", True), patch.object(
                    config, "MOCK_PIPELINE_DELAY_SEC", 0.9
                ):
                    chat = ChatController(
                        repo,
                        MockTranscriptionAdapter(transcribe_delay_sec=0.0),
                        MockSummarizationAdapter(),
                        transcription_ready=lambda: True,
                    )
                    self.chat = chat
                    chat.attach_session_id(session.id)
                    chat.stageAudioFile(str(p))
                    chat.sendPendingAudio()
                    self.assertTrue(chat.busy)
                    QTimer.singleShot(200, chat.requestStopProcessing)
                    self._pump(6.0)
                    self.assertFalse(chat.busy)
                    msgs = repo.list_messages(session.id)
                    transcripts = [
                        m
                        for m in msgs
                        if m.role == MessageRole.ASSISTANT.value
                        and m.assistant_kind == AssistantContentKind.TRANSCRIPT.value
                    ]
                    self.assertEqual(len(transcripts), 0)
                    infos = [
                        m
                        for m in msgs
                        if m.role == MessageRole.SYSTEM.value
                        and m.system_kind == MessageSystemKind.INFO.value
                    ]
                    self.assertTrue(
                        any("stopped" in (m.content or "").lower() for m in infos),
                        msg=[m.content for m in infos],
                    )
            finally:
                p.unlink(missing_ok=True)
        finally:
            tmp_out.cleanup()

    def test_stop_during_second_mock_delay_keeps_transcript(self) -> None:
        repo = InMemorySessionRepository()
        tmp_out = tempfile.TemporaryDirectory()
        repo.set_meeting_output_root(tmp_out.name)
        try:
            session = repo.create_session("stop-partial")
            wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            wav.write(b"x")
            wav.close()
            p = Path(wav.name)
            try:
                with patch.object(config, "USE_MOCK_BACKEND", True), patch.object(
                    config, "MOCK_PIPELINE_DELAY_SEC", 2.0
                ):
                    chat = ChatController(
                        repo,
                        MockTranscriptionAdapter(transcribe_delay_sec=0.0),
                        MockSummarizationAdapter(),
                        transcription_ready=lambda: True,
                    )
                    self.chat = chat
                    chat.attach_session_id(session.id)
                    chat.stageAudioFile(str(p))
                    chat.sendPendingAudio()
                    self.assertTrue(chat.busy)
                    QTimer.singleShot(2600, chat.requestStopProcessing)
                    self._pump(14.0)
                    self.assertFalse(chat.busy)
                    msgs = repo.list_messages(session.id)
                    transcripts = [
                        m
                        for m in msgs
                        if m.role == MessageRole.ASSISTANT.value
                        and m.assistant_kind == AssistantContentKind.TRANSCRIPT.value
                    ]
                    self.assertEqual(len(transcripts), 1)
                    infos = [
                        (m.content or "")
                        for m in msgs
                        if m.role == MessageRole.SYSTEM.value
                        and m.system_kind == MessageSystemKind.INFO.value
                    ]
                    self.assertTrue(
                        any("skipped" in c.lower() for c in infos),
                        msg=infos,
                    )
            finally:
                p.unlink(missing_ok=True)
        finally:
            tmp_out.cleanup()
