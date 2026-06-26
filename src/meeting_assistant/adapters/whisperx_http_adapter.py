"""HTTP client for headless WhisperX inference (Path A offline bundle host client)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from meeting_assistant.ports.speech_model_status import SpeechModelStatusSource
from meeting_assistant.ports.transcription import TranscriptionPort
from meeting_assistant.services.transcription_cancelled import TranscriptionCancelled

_log = logging.getLogger(__name__)


class RemoteWhisperStatusClient(SpeechModelStatusSource):
    """Poll the inference container for model readiness and failure hints."""

    def __init__(self, base_url: str, *, timeout_sec: float = 5.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_sec
        self._last_failure_kind = ""

    @property
    def last_failure_kind(self) -> str:
        return self._last_failure_kind

    def invalidate(self) -> None:
        return None

    def is_diarization_enabled(self) -> bool:
        status = self._fetch_status()
        return bool(status.get("diarization_enabled"))

    def is_hf_token_configured(self) -> bool:
        status = self._fetch_status()
        return bool(status.get("hf_token_configured"))

    def is_model_present(self) -> bool:
        status = self._fetch_status()
        if not status:
            return False
        self._last_failure_kind = str(status.get("last_failure_kind") or self._last_failure_kind)
        return bool(status.get("model_ready"))

    def _fetch_status(self) -> dict[str, Any]:
        url = f"{self._base}/v1/status"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                r = client.get(url)
                r.raise_for_status()
                data = r.json()
                return data if isinstance(data, dict) else {}
        except Exception as exc:
            _log.debug("Whisper API status probe failed %s: %s", url, exc)
            self._last_failure_kind = "remote"
            return {}


class WhisperHttpTranscriptionAdapter(TranscriptionPort):
    """POST audio to a headless WhisperX service and return transcript text."""

    def __init__(
        self,
        base_url: str,
        *,
        hf_token_resolver: Callable[[], str] | None = None,
        diarization_resolver: Callable[[], bool] | None = None,
        timeout_sec: float = 7200.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._hf_token_resolver = hf_token_resolver or (lambda: "")
        self._diarization_resolver = diarization_resolver or (lambda: False)
        self._timeout = timeout_sec
        self._notice_queue: list[tuple[str, str]] = []

    def consume_transcription_notices(self) -> list[tuple[str, str]]:
        out = list(self._notice_queue)
        self._notice_queue.clear()
        return out

    def release_transcription_accelerator_memory(self) -> None:
        url = f"{self._base}/v1/release-memory"
        try:
            with httpx.Client(timeout=30.0) as client:
                client.post(url)
        except Exception as exc:
            _log.debug("Whisper API release-memory failed: %s", exc)

    def transcribe(
        self,
        audio_path: Path,
        *,
        initial_prompt: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> str:
        if cancel_check is not None and cancel_check():
            raise TranscriptionCancelled()

        url = f"{self._base}/v1/transcribe"
        data: dict[str, str] = {}
        if initial_prompt:
            data["initial_prompt"] = initial_prompt
        if self._diarization_resolver():
            data["speaker_diarization"] = "1"
        token = self._hf_token_resolver().strip()
        if token:
            data["hf_token"] = token

        result: dict[str, Any] = {}
        error: dict[str, BaseException] = {}
        client_holder: dict[str, httpx.Client] = {}

        def _do_post() -> None:
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    client_holder["client"] = client
                    with audio_path.open("rb") as audio_file:
                        files = {"audio": (audio_path.name, audio_file, "application/octet-stream")}
                        response = client.post(url, data=data, files=files)
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise RuntimeError(f"Unexpected Whisper API response: {payload!r}")
                    result["payload"] = payload
            except BaseException as exc:
                error["exc"] = exc

        thread = threading.Thread(target=_do_post, daemon=True)
        thread.start()
        while thread.is_alive():
            if cancel_check is not None and cancel_check():
                client = client_holder.get("client")
                if client is not None:
                    client.close()
                raise TranscriptionCancelled()
            thread.join(timeout=0.25)

        if "exc" in error:
            raise error["exc"]

        payload = result.get("payload", {})
        text = str(payload.get("text") or "")
        notices = payload.get("notices")
        if isinstance(notices, list):
            for item in notices:
                if (
                    isinstance(item, (list, tuple))
                    and len(item) == 2
                    and isinstance(item[0], str)
                    and isinstance(item[1], str)
                ):
                    self._notice_queue.append((item[0], item[1]))
        return text
