"""Speech model cache / readiness surface for ModelStatusController."""

from __future__ import annotations

from typing import Protocol


class SpeechModelStatusSource(Protocol):
    def is_model_present(self) -> bool: ...

    def is_diarization_enabled(self) -> bool: ...

    def is_hf_token_configured(self) -> bool: ...

    @property
    def last_failure_kind(self) -> str: ...

    def invalidate(self) -> None: ...
