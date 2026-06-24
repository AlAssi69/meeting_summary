from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import is_dataclass, replace
from pathlib import Path

from meeting_assistant import config
from meeting_assistant.core.constants import MessageSystemKind
from meeting_assistant.nvidia_windows_dlls import ensure_nvidia_pip_dll_directories
from meeting_assistant.ports.audio_preparation import TranscriptionAudioPreparer
from meeting_assistant.services.diarization_format import (
    format_aligned_transcript,
    format_diarized_transcript,
)
from meeting_assistant.services.ffmpeg_audio_preprocess import resolve_ffmpeg_executable
from meeting_assistant.services.hf_token import resolve_hf_access_token
from meeting_assistant.services.transcription_audio_prep import NoOpTranscriptionAudioPreparer
from meeting_assistant.services.transcription_cancelled import TranscriptionCancelled
from meeting_assistant.services.whisperx_asr_segment_filter import filter_whisperx_asr_segments
from meeting_assistant.trace import trace_main, trace_step

_log = logging.getLogger(__name__)


def _ffmpeg_missing_message() -> str:
    return (
        "FFmpeg was not found. WhisperX uses the ffmpeg executable to decode audio. "
        "Install FFmpeg (e.g. winget install ffmpeg), ensure it is on PATH, "
        "set MEETING_ASSISTANT_FFMPEG_PATH to the full path to ffmpeg, "
        "or place ffmpeg.exe next to the application executable, then restart the app."
    )


def _require_ffmpeg_cli() -> None:
    if resolve_ffmpeg_executable() is None:
        msg = _ffmpeg_missing_message()
        _log.error(msg)
        raise RuntimeError(msg)


_GPU_FAILURE_MARKERS = (
    "cuda",
    "cudnn",
    "cublas",
    "cudart",
    "nvrtc",
    "nvidia",
    "no cuda",
    "invalid device",
    "device-side assert",
    "cudasetdevice",
    "out of memory",
    "libcudnn",
)


def _short_error(exc: BaseException, limit: int = 180) -> str:
    s = str(exc).strip().replace("\n", " ")
    if len(s) > limit:
        return s[: limit - 1] + "…"
    return s or type(exc).__name__


def _looks_like_gpu_failure(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if any(m in msg for m in _GPU_FAILURE_MARKERS):
        return True
    if isinstance(exc, OSError) and "dll" in msg:
        return True
    if isinstance(exc, ImportError) and "cuda" in msg:
        return True
    return False


def _looks_like_hf_auth_failure(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "401" in msg or "403" in msg:
        return True
    if "gated" in msg or ("accept" in msg and "conditions" in msg):
        return True
    if "could not log in" in msg or "invalid username or password" in msg:
        return True
    if "repository not found" in msg and "token" in msg:
        return True
    return False


def _torch_cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except ImportError:
        return False


def _diarize_pipeline_kwargs(hf_token: str, device: str, cache_dir: Path) -> dict:
    """Kwargs for WhisperX ``DiarizationPipeline`` (requires ``whisperx>=3.1`` ``token`` parameter)."""
    return {"device": device, "cache_dir": str(cache_dir), "token": hf_token}


class WhisperXEngine:
    """WhisperX transcription + forced alignment; optional pyannote speaker diarization."""

    def __init__(
        self,
        token_resolver: Callable[[], str] | None = None,
        *,
        diarization_resolver: Callable[[], bool] | None = None,
        audio_preparer: TranscriptionAudioPreparer | None = None,
    ) -> None:
        self._token_resolver = token_resolver or (lambda: resolve_hf_access_token(None))
        self._diarization_resolver = diarization_resolver or (
            lambda: bool(config.SPEAKER_DIARIZATION_ENABLED)
        )
        self._audio_preparer: TranscriptionAudioPreparer = (
            audio_preparer if audio_preparer is not None else NoOpTranscriptionAudioPreparer()
        )
        self._lock = threading.RLock()
        self._asr_model = None
        self._asr_device: str | None = None
        self._asr_compute_type: str | None = None
        self._forced_cpu = False
        self._warned_cuda_unavailable = False
        self._notice_queue: list[tuple[str, str]] = []
        self._last_failure_kind: str = ""

    def invalidate(self) -> None:
        with self._lock:
            self._asr_model = None
            self._asr_device = None
            self._asr_compute_type = None
            self._forced_cpu = False
            self._warned_cuda_unavailable = False
            self._notice_queue.clear()
            self._last_failure_kind = ""

    def release_loaded_asr_weights(self) -> None:
        """Drop cached ASR weights only; keep CPU fallback and notice state."""
        with self._lock:
            self._asr_model = None
            self._asr_device = None
            self._asr_compute_type = None

    def consume_transcription_notices(self) -> list[tuple[str, str]]:
        with self._lock:
            out = list(self._notice_queue)
            self._notice_queue.clear()
            return out

    @property
    def last_failure_kind(self) -> str:
        """Empty, ``weights``, or ``hf_auth`` for UI hints."""
        return self._last_failure_kind

    def is_hf_token_configured(self) -> bool:
        return bool(self._token_resolver().strip())

    def is_diarization_enabled(self) -> bool:
        return bool(self._diarization_resolver())

    def is_model_present(self) -> bool:
        if config.USE_MOCK_BACKEND:
            return True
        from meeting_assistant.services.whisper_cache_integrity import is_whisper_ct2_cache_complete

        return is_whisper_ct2_cache_complete()

    def _schedule_cpu_fallback_notice(self, exc: BaseException) -> None:
        self._notice_queue.append(
            (
                MessageSystemKind.WARNING.value,
                "GPU pipeline unavailable; continuing on CPU (slower). "
                f"Reason: {_short_error(exc)}",
            )
        )

    def _schedule_cuda_missing_notice(self) -> None:
        if self._warned_cuda_unavailable:
            return
        self._warned_cuda_unavailable = True
        self._notice_queue.append(
            (
                MessageSystemKind.INFO.value,
                "CUDA is not available (CPU-only PyTorch or GPU driver); using CPU for WhisperX.",
            )
        )

    def _ensure_asr(self, *, device: str) -> None:
        ensure_nvidia_pip_dll_directories()
        import whisperx

        lang = config.WHISPER_LANGUAGE
        asr_options: dict = {
            "beam_size": config.WHISPER_BEAM_SIZE,
            "best_of": config.WHISPER_BEAM_SIZE,
            # WhisperX's batched FasterWhisperPipeline does not apply no_speech_threshold /
            # compression_ratio_threshold during decode the way faster_whisper.WhisperModel.transcribe
            # does; we pass them for parity and apply compression / logprob filters after transcribe().
            "condition_on_previous_text": config.WHISPER_CONDITION_ON_PREVIOUS_TEXT,
            "no_speech_threshold": config.WHISPER_NO_SPEECH_THRESHOLD,
            "compression_ratio_threshold": config.WHISPER_COMPRESSION_RATIO_THRESHOLD,
        }
        candidates = config.whisper_compute_type_candidates_for_device(device)
        last_exc: BaseException | None = None
        for compute_type in candidates:
            self._asr_model = None
            try:
                self._asr_model = whisperx.load_model(
                    config.WHISPER_MODEL_SIZE,
                    device,
                    compute_type=compute_type,
                    download_root=str(config.WHISPER_DOWNLOAD_ROOT),
                    language=lang if lang else None,
                    asr_options=asr_options,
                )
                self._asr_device = device
                self._asr_compute_type = compute_type
                _log.info(
                    "Loaded WhisperX ASR %s device=%s compute_type=%s",
                    config.WHISPER_MODEL_SIZE,
                    device,
                    compute_type,
                )
                return
            except Exception as e:
                last_exc = e
                _log.info(
                    "WhisperX ASR load failed device=%s compute_type=%s: %s",
                    device,
                    compute_type,
                    e,
                )
                self._notice_queue.append(
                    (
                        MessageSystemKind.INFO.value,
                        f"Speech model: compute_type={compute_type} on {device} failed: "
                        f"{_short_error(e)}",
                    )
                )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No compute type candidates configured")

    def _ensure_model_loaded(self) -> None:
        if self._asr_model is not None:
            return

        requested = config.WHISPER_DEVICE.strip().lower()

        if self._forced_cpu or requested == "cpu":
            self._ensure_asr(device="cpu")
            return

        cuda_ok = _torch_cuda_available()
        want_gpu = requested in ("cuda", "auto")

        if want_gpu and cuda_ok:
            try:
                self._ensure_asr(device="cuda")
                return
            except Exception as e:
                _log.warning("WhisperX ASR failed on GPU (%s); falling back to CPU.", e)
                self._forced_cpu = True
                self._schedule_cpu_fallback_notice(e)
                self._ensure_asr(device="cpu")
                return

        if want_gpu and not cuda_ok:
            self._schedule_cuda_missing_notice()
            _log.info("CUDA requested but unavailable; loading WhisperX on CPU.")
        self._ensure_asr(device="cpu")

    def transcribe(
        self,
        audio_path: Path,
        *,
        initial_prompt: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> str:
        diarization_on = self.is_diarization_enabled()
        hf_token = self._token_resolver().strip()
        if diarization_on and not hf_token:
            self._last_failure_kind = "hf_auth"
            msg = (
                "Hugging Face token is not set. Speaker diarization requires a token "
                "(pyannote via WhisperX). Accept pyannote model conditions on the Hub, "
                "then set the token in Settings or MEETING_ASSISTANT_HF_TOKEN (or HF_TOKEN / HF_ACCESS_TOKEN), "
                "or disable speaker diarization in Settings."
            )
            self._notice_queue.append((MessageSystemKind.ERROR.value, msg))
            raise RuntimeError(msg)

        self._last_failure_kind = ""

        def _check_cancel() -> None:
            if cancel_check is not None and cancel_check():
                raise TranscriptionCancelled()

        with self._lock:
            try:
                return self._transcribe_locked(
                    audio_path,
                    hf_token=hf_token,
                    diarization_on=diarization_on,
                    initial_prompt=initial_prompt,
                    cancel_check=cancel_check,
                    _check_cancel=_check_cancel,
                )
            except TranscriptionCancelled:
                raise
            except Exception as e:
                if diarization_on and _looks_like_hf_auth_failure(e):
                    self._last_failure_kind = "hf_auth"
                    self._notice_queue.append(
                        (
                            MessageSystemKind.ERROR.value,
                            "Hugging Face / pyannote access failed (check token and Hub model access): "
                            f"{_short_error(e)}",
                        )
                    )
                elif _looks_like_gpu_failure(e):
                    self._last_failure_kind = "weights"
                else:
                    self._last_failure_kind = ""
                raise

    def _transcribe_locked(
        self,
        audio_path: Path,
        *,
        hf_token: str,
        diarization_on: bool,
        initial_prompt: str | None,
        cancel_check: Callable[[], bool] | None,
        _check_cancel: Callable[[], None],
    ) -> str:
        import whisperx

        self._ensure_model_loaded()
        assert self._asr_model is not None
        device = self._asr_device or "cpu"
        batch_size = max(1, config.WHISPERX_TRANSCRIBE_BATCH_SIZE)
        trace_main(
            "WhisperX pipeline start file=%s device=%s batch_size=%d",
            audio_path.name,
            device,
            batch_size,
        )

        if hasattr(self._asr_model, "options"):
            opts = self._asr_model.options
            ip = (initial_prompt or "").strip() or None
            try:
                if is_dataclass(opts):
                    self._asr_model.options = replace(opts, initial_prompt=ip)
                else:
                    setattr(opts, "initial_prompt", ip)
            except Exception:
                try:
                    setattr(opts, "initial_prompt", ip)
                except Exception:
                    pass

        _require_ffmpeg_cli()
        with self._audio_preparer.prepare(audio_path) as effective_path:
            t_load0 = time.perf_counter()
            try:
                audio = whisperx.load_audio(str(effective_path))
            except FileNotFoundError as e:
                raise RuntimeError(_ffmpeg_missing_message()) from e
            _check_cancel()
            t_load1 = time.perf_counter()
            n_samples = int(getattr(audio, "shape", [len(audio)])[0])
            dur_sec = n_samples / 16000.0
            trace_step(
                "WhisperX load_audio done samples=%d duration_sec=%.2f elapsed_sec=%.2f",
                n_samples,
                dur_sec,
                t_load1 - t_load0,
            )

            t_asr0 = time.perf_counter()
            result = self._asr_model.transcribe(audio, batch_size=batch_size)
            raw_segments = list(result.get("segments") or [])
            result["segments"] = filter_whisperx_asr_segments(
                raw_segments,
                compression_ratio_threshold=config.WHISPER_COMPRESSION_RATIO_THRESHOLD,
                compression_min_chars=config.WHISPERX_ASR_COMPRESSION_FILTER_MIN_CHARS,
                min_avg_logprob=config.WHISPERX_DROP_SEGMENT_MIN_AVG_LOGPROB,
            )
            t_asr1 = time.perf_counter()
            _check_cancel()
            n_seg = len(result.get("segments") or [])
            trace_main("WhisperX ASR transcribe done elapsed_sec=%.2f segments=%d", t_asr1 - t_asr0, n_seg)

            # Alignment: optional fixed language (e.g. ar) while ASR may use auto-detect.
            raw_lang = result.get("language")
            detected = raw_lang.strip() if isinstance(raw_lang, str) and raw_lang.strip() else "en"
            language_code = config.WHISPER_ALIGN_LANGUAGE or detected
            t_al0 = time.perf_counter()
            model_a, metadata = whisperx.load_align_model(language_code=language_code, device=device)
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                device,
                return_char_alignments=False,
            )
            t_al1 = time.perf_counter()
            _check_cancel()
            trace_main(
                "WhisperX align done language=%s elapsed_sec=%.2f",
                language_code,
                t_al1 - t_al0,
            )

            segments = result.get("segments") or []
            if diarization_on:
                # Diarization (pyannote via HF token) — same effective_path as ASR / align
                from whisperx.diarize import DiarizationPipeline

                d_kw = _diarize_pipeline_kwargs(hf_token, device, config.WHISPER_DOWNLOAD_ROOT)
                t_d0 = time.perf_counter()
                diarize_model = DiarizationPipeline(**d_kw)
                diarize_df = diarize_model(str(effective_path))
                t_d1 = time.perf_counter()
                _check_cancel()
                trace_main("WhisperX diarize done elapsed_sec=%.2f", t_d1 - t_d0)

                t_m0 = time.perf_counter()
                result = whisperx.assign_word_speakers(diarize_df, result)
                t_m1 = time.perf_counter()
                trace_main("WhisperX assign_word_speakers done elapsed_sec=%.2f", t_m1 - t_m0)
                segments = result.get("segments") or []

            if cancel_check is not None:
                for _ in segments:
                    if cancel_check():
                        raise TranscriptionCancelled()

            if diarization_on:
                text = format_diarized_transcript(segments)
            else:
                text = format_aligned_transcript(segments)
            if not text or text == "(No speech detected)":
                _log.warning("Empty or no speech for %s", audio_path)
            return text or "(No speech detected)"
