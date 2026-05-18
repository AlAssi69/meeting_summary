"""Central dummy copy for mock STT/LLM (single place to trim for production)."""

MOCK_TRANSCRIPT: str = (
    "SPEAKER_00 [00:00 - 00:05]: [Mock transcript] First speaker line from the mock adapter.\n\n"
    "SPEAKER_01 [00:05 - 00:12]: Second speaker line — set MEETING_ASSISTANT_MOCK=0 for WhisperX on real audio."
)

MOCK_SUMMARY: str = (
    "[Mock summary] Executive summary: (placeholder). "
    "Action items: 1) Enable Ollama on 127.0.0.1:11434. 2) Set MEETING_ASSISTANT_MOCK=0."
)
