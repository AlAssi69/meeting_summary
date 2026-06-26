"""Headless WhisperX HTTP API for offline inference containers (Path A)."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from meeting_assistant import config
from meeting_assistant.services.transcription_audio_prep import build_transcription_audio_preparer
from meeting_assistant.services.transcription_cancelled import TranscriptionCancelled
from meeting_assistant.services.whisperx_engine import WhisperXEngine

_log = logging.getLogger(__name__)

app = FastAPI(title="Meeting Assistant WhisperX API", version="1.0.0")

_engine: WhisperXEngine | None = None
_diarization_override: bool | None = None
_hf_token_override: str | None = None


def _token_resolver() -> str:
    if _hf_token_override:
        return _hf_token_override
    return (os.environ.get("MEETING_ASSISTANT_HF_TOKEN") or config.HF_ACCESS_TOKEN or "").strip()


def _diarization_resolver() -> bool:
    if _diarization_override is not None:
        return _diarization_override
    return config.SPEAKER_DIARIZATION_ENABLED


def get_engine() -> WhisperXEngine:
    global _engine
    if _engine is None:
        _engine = WhisperXEngine(
            token_resolver=_token_resolver,
            diarization_resolver=_diarization_resolver,
            audio_preparer=build_transcription_audio_preparer(),
        )
    return _engine


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/status")
def status() -> dict[str, Any]:
    engine = get_engine()
    return {
        "model_ready": engine.is_model_present(),
        "whisper_model": config.WHISPER_MODEL_SIZE,
        "whisper_device": config.WHISPER_DEVICE,
        "align_language": config.WHISPER_ALIGN_LANGUAGE,
        "diarization_enabled": engine.is_diarization_enabled(),
        "hf_token_configured": engine.is_hf_token_configured(),
        "last_failure_kind": engine.last_failure_kind,
        "offline_bundle": config.OFFLINE_BUNDLE,
    }


@app.post("/v1/release-memory")
def release_memory() -> dict[str, str]:
    engine = get_engine()
    engine.release_loaded_asr_weights()
    from meeting_assistant.services.gpu_memory import collect_and_empty_torch_cuda_cache

    collect_and_empty_torch_cuda_cache()
    return {"status": "released"}


@app.post("/v1/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    initial_prompt: str = Form(""),
    speaker_diarization: str = Form(""),
    hf_token: str = Form(""),
) -> JSONResponse:
    global _diarization_override, _hf_token_override

    suffix = Path(audio.filename or "audio.bin").suffix or ".wav"
    engine = get_engine()

    prev_diarization = _diarization_override
    prev_token = _hf_token_override
    try:
        if speaker_diarization.strip().lower() in {"1", "true", "yes", "on"}:
            _diarization_override = True
        if hf_token.strip():
            _hf_token_override = hf_token.strip()

        fd, temp_name = tempfile.mkstemp(suffix=suffix, prefix="whisper_api_")
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            content = await audio.read()
            temp_path.write_bytes(content)
            prompt = initial_prompt.strip() or None
            text = engine.transcribe(temp_path, initial_prompt=prompt)
            notices = engine.consume_transcription_notices()
            return JSONResponse(
                {
                    "text": text,
                    "notices": [list(pair) for pair in notices],
                    "last_failure_kind": engine.last_failure_kind,
                }
            )
        except TranscriptionCancelled:
            return JSONResponse({"error": "cancelled"}, status_code=499)
        except Exception as exc:
            _log.exception("Transcription failed")
            notices = engine.consume_transcription_notices()
            return JSONResponse(
                {
                    "error": str(exc),
                    "notices": [list(pair) for pair in notices],
                    "last_failure_kind": engine.last_failure_kind,
                },
                status_code=500,
            )
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
    finally:
        _diarization_override = prev_diarization
        _hf_token_override = prev_token
