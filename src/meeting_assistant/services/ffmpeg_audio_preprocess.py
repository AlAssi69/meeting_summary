"""FFmpeg invocation for transcription-oriented WAV preprocessing (single responsibility)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

from meeting_assistant import config

# Dedicated channel: short logger name + banners + "| AUDIO-PREP |" lines scan easily in the terminal.
_PREP = logging.getLogger("meeting_assistant.audio_prep")
_RULE = "#" * 78


def log_audio_prep_banner_start(*, input_name: str, temp_name: str) -> None:
    """Open a highly visible block before FFmpeg runs."""
    _PREP.info(_RULE)
    _PREP.info("##  AUDIO PREPROCESSING (FFmpeg)  —  original file is NOT modified  ##########")
    _PREP.info(_RULE)
    _PREP.info("| AUDIO-PREP | Input (read-only):  %s", input_name)
    _PREP.info("| AUDIO-PREP | Temp WAV path:      %s", temp_name)


def log_audio_prep_banner_end_ok(*, elapsed_sec: float, output_bytes: int) -> None:
    _PREP.info("| AUDIO-PREP | FFmpeg finished in %.2fs | output size: %d bytes", elapsed_sec, output_bytes)
    _PREP.info("| AUDIO-PREP | Next: load cleaned audio into the speech model.")
    _PREP.info(_RULE)
    _PREP.info("##  END AUDIO PREPROCESSING  (success)  ######################################")
    _PREP.info(_RULE)


def log_audio_prep_banner_end_failed(*, headline: str, detail: str = "") -> None:
    _PREP.info(_RULE)
    _PREP.info("##  END AUDIO PREPROCESSING  (FAILED)  ########################################")
    _PREP.error("| AUDIO-PREP | %s", headline)
    if detail:
        _PREP.error("| AUDIO-PREP | %s", detail[:4000] if len(detail) > 4000 else detail)
    _PREP.info(_RULE)


def log_audio_prep_temp_removed(temp_name: str) -> None:
    _PREP.info("| AUDIO-PREP | Removed temporary file: %s", temp_name)


def log_audio_prep_skipped(*, source_name: str) -> None:
    """When preprocessing is disabled — one line, easy to grep without banner noise."""
    _PREP.info(
        "| AUDIO-PREP | Skipped (MEETING_ASSISTANT_AUDIO_PREP_ENABLED=0) — ASR uses original: %s",
        source_name,
    )


def log_audio_prep_keep_temp_notice(path: str) -> None:
    _PREP.warning("| AUDIO-PREP | KEEP_TEMP enabled — leaving file on disk: %s", path)


def resolve_ffmpeg_executable() -> Path | None:
    """Resolve ffmpeg: env override, then next to frozen/sys.executable, then PATH."""
    raw = (config.FFMPEG_PATH or "").strip()
    if raw:
        p = Path(raw)
        if p.is_file():
            return p.resolve()
    exe_dir = Path(sys.executable).resolve().parent
    for name in ("ffmpeg.exe", "ffmpeg"):
        candidate = exe_dir / name
        if candidate.is_file():
            return candidate.resolve()
    w = shutil.which("ffmpeg")
    if w:
        return Path(w).resolve()
    return None


def build_transcription_afilter(
    *,
    override: str,
    highpass_hz: float,
    threshold_db: float,
    ratio: float,
    attack_ms: float,
    release_ms: float,
    makeup_db: float,
    loudnorm_enabled: bool,
    loudnorm_i: float,
    loudnorm_tp: float,
    loudnorm_lra: float,
) -> str:
    """Return the ``-af`` argument. ``override`` wins when non-empty (advanced users)."""
    if override.strip():
        return override.strip()
    parts: list[str] = []
    if highpass_hz > 0:
        parts.append(f"highpass=f={highpass_hz}")
    parts.append(
        "acompressor="
        f"threshold={threshold_db}dB:ratio={ratio}:attack={attack_ms}:release={release_ms}:makeup={makeup_db}dB"
    )
    if loudnorm_enabled:
        parts.append(f"loudnorm=I={loudnorm_i}:TP={loudnorm_tp}:LRA={loudnorm_lra}")
    return ",".join(parts)


def build_transcription_afilter_from_config() -> str:
    return build_transcription_afilter(
        override=config.AUDIO_PREP_FFMPEG_AFILTER,
        highpass_hz=config.AUDIO_PREP_HIGHPASS_HZ,
        threshold_db=config.AUDIO_PREP_ACOMP_THRESHOLD_DB,
        ratio=config.AUDIO_PREP_ACOMP_RATIO,
        attack_ms=config.AUDIO_PREP_ACOMP_ATTACK_MS,
        release_ms=config.AUDIO_PREP_ACOMP_RELEASE_MS,
        makeup_db=config.AUDIO_PREP_ACOMP_MAKEUP_DB,
        loudnorm_enabled=config.AUDIO_PREP_LOUDNORM_ENABLED,
        loudnorm_i=config.AUDIO_PREP_LOUDNORM_I,
        loudnorm_tp=config.AUDIO_PREP_LOUDNORM_TP,
        loudnorm_lra=config.AUDIO_PREP_LOUDNORM_LRA,
    )


def ffmpeg_cli_available() -> bool:
    return resolve_ffmpeg_executable() is not None


def log_audio_prep_pipeline_stages() -> None:
    """Log each preprocessing stage and its purpose (terminal debugging)."""
    _PREP.info("| AUDIO-PREP | --- Filter chain (what & why) ---")
    override = (config.AUDIO_PREP_FFMPEG_AFILTER or "").strip()
    if override:
        _PREP.info(
            "| AUDIO-PREP | [custom -af] MEETING_ASSISTANT_FFMPEG_AFILTER replaces the built-in chain."
        )
        _PREP.debug("| AUDIO-PREP | Custom -af value: %s", override)
        _PREP.info(
            "| AUDIO-PREP | [encode] Resample to %d Hz, mono, pcm_s16le — Whisper / WhisperX input format.",
            config.AUDIO_PREP_OUTPUT_SAMPLE_RATE,
        )
        return

    if config.AUDIO_PREP_HIGHPASS_HZ > 0:
        _PREP.info(
            "| AUDIO-PREP | [highpass %.1f Hz] Cut rumble / HVAC / handling noise before dynamics and ASR.",
            config.AUDIO_PREP_HIGHPASS_HZ,
        )
    else:
        _PREP.info("| AUDIO-PREP | [highpass] OFF (HIGHPASS_HZ=0).")

    _PREP.info(
        "| AUDIO-PREP | [acompressor] Evens quiet vs loud speech so the model sees a steadier level."
    )
    _PREP.debug(
        "| AUDIO-PREP |     compressor: threshold=%.1f dB ratio=%.2f attack=%.1f ms release=%.1f ms makeup=%.1f dB",
        config.AUDIO_PREP_ACOMP_THRESHOLD_DB,
        config.AUDIO_PREP_ACOMP_RATIO,
        config.AUDIO_PREP_ACOMP_ATTACK_MS,
        config.AUDIO_PREP_ACOMP_RELEASE_MS,
        config.AUDIO_PREP_ACOMP_MAKEUP_DB,
    )

    if config.AUDIO_PREP_LOUDNORM_ENABLED:
        _PREP.info(
            "| AUDIO-PREP | [loudnorm] EBU-style targets I=%.1f LUFS TP=%.1f dBTP LRA=%.1f — stable loudness for decode.",
            config.AUDIO_PREP_LOUDNORM_I,
            config.AUDIO_PREP_LOUDNORM_TP,
            config.AUDIO_PREP_LOUDNORM_LRA,
        )
    else:
        _PREP.info("| AUDIO-PREP | [loudnorm] OFF — no loudness normalization after compression.")

    _PREP.info(
        "| AUDIO-PREP | [encode] Resample to %d Hz, mono, pcm_s16le — format conformity for the speech stack.",
        config.AUDIO_PREP_OUTPUT_SAMPLE_RATE,
    )


def run_ffmpeg_transcription_prep(
    input_path: Path,
    output_path: Path,
    *,
    afilter: str,
    sample_rate: int,
    timeout_sec: float,
) -> None:
    """Run FFmpeg to write a mono PCM WAV at ``sample_rate``. Raises ``RuntimeError`` on failure."""
    ffmpeg_exe = resolve_ffmpeg_executable()
    if ffmpeg_exe is None:
        msg = "ffmpeg not found (set MEETING_ASSISTANT_FFMPEG_PATH, place ffmpeg beside the app, or install on PATH)."
        log_audio_prep_banner_end_failed(headline=msg)
        raise RuntimeError(msg)
    _PREP.info("| AUDIO-PREP | FFmpeg binary: %s", ffmpeg_exe)
    log_audio_prep_pipeline_stages()
    _PREP.info("| AUDIO-PREP | -af %s", afilter)
    argv = [
        str(ffmpeg_exe),
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(input_path),
        "-af",
        afilter,
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    _PREP.debug("| AUDIO-PREP | argv=%s", argv)
    _PREP.info("| AUDIO-PREP | Running FFmpeg subprocess…")
    t0 = time.perf_counter()
    try:
        cp = subprocess.run(
            argv,
            capture_output=True,
            timeout=timeout_sec,
            text=True,
        )
    except subprocess.TimeoutExpired as e:
        elapsed = time.perf_counter() - t0
        log_audio_prep_banner_end_failed(
            headline=f"FFmpeg timed out after {timeout_sec:.1f}s (elapsed {elapsed:.2f}s).",
            detail=str(input_path),
        )
        raise RuntimeError("FFmpeg audio preprocessing timed out") from e
    elapsed = time.perf_counter() - t0
    if cp.returncode != 0:
        err_tail = (cp.stderr or "")[-2000:]
        log_audio_prep_banner_end_failed(
            headline=f"FFmpeg failed (exit {cp.returncode}).",
            detail=err_tail,
        )
        raise RuntimeError("FFmpeg audio preprocessing failed")
    try:
        out_size = output_path.stat().st_size
    except OSError:
        out_size = -1
    log_audio_prep_banner_end_ok(elapsed_sec=elapsed, output_bytes=out_size)
