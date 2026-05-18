from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from meeting_assistant.ports.transcription import TranscriptionPort
from meeting_assistant.services.gpu_memory import collect_and_empty_torch_cuda_cache
from meeting_assistant.services.whisperx_engine import WhisperXEngine

_log = logging.getLogger(__name__)


class WhisperXTranscriptionAdapter(TranscriptionPort):
    """WhisperX ASR + alignment + pyannote diarization; returns SPEAKER_XX transcript lines."""

    def __init__(self, engine: WhisperXEngine) -> None:
        self._engine = engine

    def transcribe(
        self,
        audio_path: Path,
        *,
        initial_prompt: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> str:
        return self._engine.transcribe(
            audio_path, initial_prompt=initial_prompt, cancel_check=cancel_check
        )

    def release_transcription_accelerator_memory(self) -> None:
        self._engine.release_loaded_asr_weights()
        collect_and_empty_torch_cuda_cache()

    def consume_transcription_notices(self) -> list[tuple[str, str]]:
        return self._engine.consume_transcription_notices()
