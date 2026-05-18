from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from meeting_assistant.adapters.mock_data import MOCK_TRANSCRIPT
from meeting_assistant.ports.transcription import TranscriptionPort
from meeting_assistant.services.transcription_cancelled import TranscriptionCancelled

_log = logging.getLogger(__name__)


class MockTranscriptionAdapter(TranscriptionPort):
    def __init__(self, transcribe_delay_sec: float = 0.0) -> None:
        self._transcribe_delay_sec = transcribe_delay_sec

    def transcribe(
        self,
        audio_path: Path,
        *,
        initial_prompt: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> str:
        _log.debug("Mock transcribe: %s", audio_path)
        if self._transcribe_delay_sec > 0:
            deadline = time.monotonic() + self._transcribe_delay_sec
            while time.monotonic() < deadline:
                if cancel_check is not None and cancel_check():
                    raise TranscriptionCancelled()
                time.sleep(0.05)
        if cancel_check is not None and cancel_check():
            raise TranscriptionCancelled()
        return MOCK_TRANSCRIPT

    def release_transcription_accelerator_memory(self) -> None:
        pass
