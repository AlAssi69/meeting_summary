"""Tests for offline Path A HTTP transcription wiring."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from meeting_assistant.adapters.whisperx_http_adapter import (
    RemoteWhisperStatusClient,
    WhisperHttpTranscriptionAdapter,
)


def test_remote_status_client_handles_unreachable_api() -> None:
    client = RemoteWhisperStatusClient("http://127.0.0.1:59999", timeout_sec=0.5)
    assert client.is_model_present() is False
    assert client.last_failure_kind == "remote"


def test_whisper_http_transcribe_posts_multipart(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"RIFF")

    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"text": "hello", "notices": [["info", "ok"]]}

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, data: dict[str, str], files: dict) -> FakeResponse:
            captured["url"] = url
            captured["data"] = data
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    adapter = WhisperHttpTranscriptionAdapter("http://127.0.0.1:18080")
    text = adapter.transcribe(audio, initial_prompt="glossary")
    assert text == "hello"
    assert captured["url"] == "http://127.0.0.1:18080/v1/transcribe"
    assert captured["data"] == {"initial_prompt": "glossary"}
    assert adapter.consume_transcription_notices() == [("info", "ok")]
