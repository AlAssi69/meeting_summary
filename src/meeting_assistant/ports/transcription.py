from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class TranscriptionPort(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        *,
        initial_prompt: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> str: ...

    def release_transcription_accelerator_memory(self) -> None:
        """Drop loaded speech model weights and free accelerator memory when safe."""
        ...
