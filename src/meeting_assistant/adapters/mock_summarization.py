from __future__ import annotations

import logging

from meeting_assistant.adapters.mock_data import MOCK_SUMMARY
from meeting_assistant.ports.summarization import SummarizationPort

_log = logging.getLogger(__name__)


class MockSummarizationAdapter(SummarizationPort):
    def summarize(self, transcript: str, system_prompt: str) -> str:
        _log.debug(
            "Mock summarize, prompt_len=%s transcript_len=%s",
            len(system_prompt),
            len(transcript),
        )
        return MOCK_SUMMARY
