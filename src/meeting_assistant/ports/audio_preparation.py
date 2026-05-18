"""Strategy for optional audio normalization before transcription."""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol


class TranscriptionAudioPreparer(Protocol):
    """Yields a filesystem path to audio suitable for ASR (and diarization when applicable)."""

    def prepare(self, source: Path) -> AbstractContextManager[Path]:
        """Context manager: yield path to use; cleanup temporary files after exit."""
