from __future__ import annotations

import logging
from typing import Any

import httpx

from meeting_assistant import config
from meeting_assistant.ports.summarization import SummarizationPort
from meeting_assistant.services.prompt_composition import compose_llm_user_content
from meeting_assistant.trace import trace_dump, trace_step

_log = logging.getLogger(__name__)


class OllamaSummarizationAdapter(SummarizationPort):
    """HTTP client for Ollama. Base URL comes from config (see MEETING_ASSISTANT_OLLAMA_*)."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self._base = (base_url or config.OLLAMA_BASE_URL).rstrip("/")
        self._model = model or config.OLLAMA_MODEL

    def summarize(self, transcript: str, system_prompt: str) -> str:
        user_content = compose_llm_user_content(transcript)
        url = f"{self._base}/api/chat"
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
        }
        trace_step("Ollama POST %s model=%s", url, self._model)
        trace_dump("Ollama chat request stream=%s", body.get("stream"))
        with httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
            r = client.post(url, json=body)
            r.raise_for_status()
            data = r.json()
        trace_dump("Ollama chat response keys=%s", sorted(data.keys()))
        msg = data.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        # Fallback for generate-style responses if misconfigured
        if isinstance(data.get("response"), str):
            return str(data["response"]).strip()
        raise RuntimeError(f"Unexpected Ollama response: {data!r}")
