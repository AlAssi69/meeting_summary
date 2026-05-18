from __future__ import annotations

from typing import Protocol


class SummarizationPort(Protocol):
    def summarize(self, transcript: str, system_prompt: str) -> str: ...
