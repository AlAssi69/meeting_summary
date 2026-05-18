"""Application configuration. Prefer env vars for paths and feature flags."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _project_root() -> Path:
    """Repository root (folder containing ``main.py``)."""
    return Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """Load ``.env`` from the project root into the process environment (optional dependency).

    Existing OS environment variables win (``override=False``).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_file = _project_root() / ".env"
    if env_file.is_file():
        load_dotenv(env_file, override=False)


_load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return default


# User-visible debug dialogs/toasts (grep for [DEBUG] or MEETING_ASSISTANT_DEBUG)
DEBUG_UI: bool = _env_bool("MEETING_ASSISTANT_DEBUG", False)


def _clamp_int_env(raw: str, *, lo: int, hi: int, default: int) -> int:
    try:
        v = int(raw.strip())
    except ValueError:
        return default
    return max(lo, min(hi, v))


# Terminal trace verbosity for tests and troubleshooting (separate from DEBUG_UI).
# Canonical: MEETING_ASSISTANT_TRACE_LEVEL=0..3 (0=default logging; 1=main pipeline steps;
# 2=sub-steps and I/O; 3=fine-grained app diagnostics). If unset, MEETING_ASSISTANT_VERBOSE
# is used as an alias (same 0..3). When both are set, TRACE_LEVEL wins.
_trace_level_raw = (os.environ.get("MEETING_ASSISTANT_TRACE_LEVEL") or "").strip()
_verbose_level_raw = (os.environ.get("MEETING_ASSISTANT_VERBOSE") or "").strip()
if _trace_level_raw:
    TRACE_LEVEL: int = _clamp_int_env(_trace_level_raw, lo=0, hi=3, default=0)
elif _verbose_level_raw:
    TRACE_LEVEL = _clamp_int_env(_verbose_level_raw, lo=0, hi=3, default=0)
else:
    TRACE_LEVEL = 0

# When True, use mock transcription/summarization and in-memory session store.
# Set MEETING_ASSISTANT_MOCK=0 to use SQLite + WhisperX + Ollama.
USE_MOCK_BACKEND: bool = _env_bool("MEETING_ASSISTANT_MOCK", False)

def _hf_access_token_from_env() -> str:
    """HF token: first non-empty among app-specific and common Hub env names (after ``.env`` load)."""
    for key in (
        "MEETING_ASSISTANT_HF_TOKEN",
        "HF_ACCESS_TOKEN",
        "HUGGING_FACE_HUB_TOKEN",
        "HF_TOKEN",
    ):
        v = (os.environ.get(key) or "").strip()
        if v:
            return v
    return ""


# Hugging Face token: required for real WhisperX transcription (pyannote diarization in the same path).
# Set in ``.env`` (see ``MEETING_ASSISTANT_HF_TOKEN``) or in the real environment; Settings can override when non-empty.
HF_ACCESS_TOKEN: str = _hf_access_token_from_env()

# Ollama — Windows + WSL2: use "localhost" so host port forwarding reaches the service;
# on Linux/macOS default 127.0.0.1 matches a typical local bind. Override with env vars.
_default_ollama_host = "localhost" if sys.platform == "win32" else "127.0.0.1"
OLLAMA_HOST: str = os.environ.get("MEETING_ASSISTANT_OLLAMA_HOST", _default_ollama_host)
OLLAMA_PORT: int = int(os.environ.get("MEETING_ASSISTANT_OLLAMA_PORT", "11434"))
_ollama_base_url_env = os.environ.get("MEETING_ASSISTANT_OLLAMA_BASE_URL", "").strip()
OLLAMA_BASE_URL: str = (
    _ollama_base_url_env.rstrip("/")
    if _ollama_base_url_env
    else f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
)

OLLAMA_MODEL: str = os.environ.get("MEETING_ASSISTANT_OLLAMA_MODEL", "gemma4:e4b128k")

# Repo root (portable models, etc.). Override when the app bundle layout differs.
_PROJECT_DEFAULT = _project_root()
PROJECT_ROOT: Path = Path(os.environ.get("MEETING_ASSISTANT_PROJECT_ROOT", str(_PROJECT_DEFAULT)))

# faster-whisper CT2 repos — must stay aligned with faster_whisper.utils._MODELS
FASTER_WHISPER_HF_REPOS: dict[str, str] = {
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "tiny": "Systran/faster-whisper-tiny",
    "base.en": "Systran/faster-whisper-base.en",
    "base": "Systran/faster-whisper-base",
    "small.en": "Systran/faster-whisper-small.en",
    "small": "Systran/faster-whisper-small",
    "medium.en": "Systran/faster-whisper-medium.en",
    "medium": "Systran/faster-whisper-medium",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large": "Systran/faster-whisper-large-v3",
    "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
    "distil-medium.en": "Systran/faster-distil-whisper-medium.en",
    "distil-small.en": "Systran/faster-distil-whisper-small.en",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
    "distil-large-v3.5": "distil-whisper/distil-large-v3.5-ct2",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}

WHISPER_MODEL_SIZE: str = os.environ.get("MEETING_ASSISTANT_WHISPER_MODEL", "large-v3")
WHISPER_DOWNLOAD_ROOT: Path = Path(
    os.environ.get("MEETING_ASSISTANT_WHISPER_CACHE", str(PROJECT_ROOT / "models" / "whisper"))
)

# MEETING_ASSISTANT_WHISPER_LANGUAGE=ar | auto (default) | empty for auto-detect ASR language
_whisper_lang_raw = os.environ.get("MEETING_ASSISTANT_WHISPER_LANGUAGE", "auto").strip().lower()
WHISPER_LANGUAGE: str | None = None if _whisper_lang_raw in ("", "auto", "none") else _whisper_lang_raw

# WhisperX alignment only: ISO-639-1 code for load_align_model. Empty / auto / none = use ASR-detected language.
_whisper_align_raw = os.environ.get("MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE", "ar").strip().lower()
WHISPER_ALIGN_LANGUAGE: str | None = (
    None if _whisper_align_raw in ("", "auto", "none") else _whisper_align_raw
)

# Optional post-transcription Ollama pass: fix Arabized English jargon using the same Whisper glossary text.
TRANSCRIPT_JARGON_NORMALIZE: bool = _env_bool("MEETING_ASSISTANT_TRANSCRIPT_JARGON_NORMALIZE", False)

# Beam search width (default 7 for GPU and CPU). Optional override via MEETING_ASSISTANT_WHISPER_BEAM_SIZE.
_whisper_beam_raw = int(os.environ.get("MEETING_ASSISTANT_WHISPER_BEAM_SIZE", "7"))
WHISPER_BEAM_SIZE: int = max(1, min(16, _whisper_beam_raw))

# Anti-hallucination / decoding (faster-whisper; WhisperX ASR uses asr_options + post-filter where noted).
# Defaults favor fewer hallucinations: no cross-window conditioning, stricter speech-vs-noise (0.75),
# standard repetition filter (2.4). Override via MEETING_ASSISTANT_WHISPER_* when needed.
WHISPER_CONDITION_ON_PREVIOUS_TEXT: bool = _env_bool(
    "MEETING_ASSISTANT_WHISPER_CONDITION_ON_PREVIOUS_TEXT", default=False
)


def _whisper_float_env(name: str, default: float, *, lo: float, hi: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        v = float(raw)
    except ValueError:
        return default
    return max(lo, min(hi, v))


WHISPER_NO_SPEECH_THRESHOLD: float = _whisper_float_env(
    "MEETING_ASSISTANT_WHISPER_NO_SPEECH_THRESHOLD",
    0.75,
    lo=0.0,
    hi=1.0,
)
WHISPER_COMPRESSION_RATIO_THRESHOLD: float = _whisper_float_env(
    "MEETING_ASSISTANT_WHISPER_COMPRESSION_RATIO_THRESHOLD",
    2.4,
    lo=1.0,
    hi=10.0,
)


def _optional_float_env(name: str) -> float | None:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


# WhisperX: optional drop when avg_logprob is below this (negative values typical). Unset = disabled.
WHISPERX_DROP_SEGMENT_MIN_AVG_LOGPROB: float | None = _optional_float_env(
    "MEETING_ASSISTANT_WHISPERX_DROP_SEGMENT_MIN_AVG_LOGPROB"
)

# Only apply compression-ratio drop when segment text is at least this long (short lines are noisy).
try:
    _whisperx_comp_min_chars_raw = int(
        os.environ.get("MEETING_ASSISTANT_WHISPERX_ASR_COMPRESSION_MIN_CHARS", "24")
    )
except ValueError:
    _whisperx_comp_min_chars_raw = 24
WHISPERX_ASR_COMPRESSION_FILTER_MIN_CHARS: int = max(0, min(1000, _whisperx_comp_min_chars_raw))

# cpu | cuda | auto — passed to WhisperX / CTranslate2 (GPU-first default: cuda)
WHISPER_DEVICE: str = os.environ.get("MEETING_ASSISTANT_WHISPER_DEVICE", "cuda").strip().lower()

# WhisperX ASR batch size (reduce on low VRAM).
_WHISPERX_BATCH_RAW = int(os.environ.get("MEETING_ASSISTANT_WHISPERX_BATCH_SIZE", "8"))
WHISPERX_TRANSCRIBE_BATCH_SIZE: int = max(1, min(64, _WHISPERX_BATCH_RAW))

# Optional path to ffmpeg executable (overrides frozen-dir and PATH lookup). Same resolver used for WhisperX decode checks.
FFMPEG_PATH: str = (os.environ.get("MEETING_ASSISTANT_FFMPEG_PATH") or "").strip()

# --- FFmpeg preprocessing (16 kHz mono WAV for Whisper / WhisperX; on by default) ---
AUDIO_PREP_ENABLED: bool = _env_bool("MEETING_ASSISTANT_AUDIO_PREP_ENABLED", True)
AUDIO_PREP_KEEP_TEMP: bool = _env_bool("MEETING_ASSISTANT_AUDIO_PREP_KEEP_TEMP", False)
# Whisper expects 16 kHz internally; keep fixed unless you know what you are doing.
AUDIO_PREP_OUTPUT_SAMPLE_RATE: int = 16000
AUDIO_PREP_FFMPEG_TIMEOUT_SEC: float = _whisper_float_env(
    "MEETING_ASSISTANT_AUDIO_PREP_FFMPEG_TIMEOUT_SEC",
    7200.0,
    lo=30.0,
    hi=86400.0,
)
# Non-empty: use as full -af filter string (overrides structured highpass + compressor below).
AUDIO_PREP_FFMPEG_AFILTER: str = (os.environ.get("MEETING_ASSISTANT_FFMPEG_AFILTER") or "").strip()
AUDIO_PREP_HIGHPASS_HZ: float = _whisper_float_env(
    "MEETING_ASSISTANT_AUDIO_PREP_HIGHPASS_HZ",
    80.0,
    lo=0.0,
    hi=500.0,
)
AUDIO_PREP_ACOMP_THRESHOLD_DB: float = _whisper_float_env(
    "MEETING_ASSISTANT_AUDIO_PREP_ACOMP_THRESHOLD_DB",
    -18.0,
    lo=-80.0,
    hi=0.0,
)
AUDIO_PREP_ACOMP_RATIO: float = _whisper_float_env(
    "MEETING_ASSISTANT_AUDIO_PREP_ACOMP_RATIO",
    3.0,
    lo=1.0,
    hi=20.0,
)
AUDIO_PREP_ACOMP_ATTACK_MS: float = _whisper_float_env(
    "MEETING_ASSISTANT_AUDIO_PREP_ACOMP_ATTACK_MS",
    20.0,
    lo=0.1,
    hi=2000.0,
)
AUDIO_PREP_ACOMP_RELEASE_MS: float = _whisper_float_env(
    "MEETING_ASSISTANT_AUDIO_PREP_ACOMP_RELEASE_MS",
    250.0,
    lo=1.0,
    hi=5000.0,
)
AUDIO_PREP_ACOMP_MAKEUP_DB: float = _whisper_float_env(
    "MEETING_ASSISTANT_AUDIO_PREP_ACOMP_MAKEUP_DB",
    2.0,
    lo=-12.0,
    hi=24.0,
)
# EBU R128 single-pass loudnorm after dynamics (structured -af only; full MEETING_ASSISTANT_FFMPEG_AFILTER overrides entire chain).
AUDIO_PREP_LOUDNORM_ENABLED: bool = _env_bool("MEETING_ASSISTANT_AUDIO_PREP_LOUDNORM_ENABLED", True)
AUDIO_PREP_LOUDNORM_I: float = _whisper_float_env(
    "MEETING_ASSISTANT_AUDIO_PREP_LOUDNORM_I",
    -16.0,
    lo=-70.0,
    hi=-5.0,
)
AUDIO_PREP_LOUDNORM_TP: float = _whisper_float_env(
    "MEETING_ASSISTANT_AUDIO_PREP_LOUDNORM_TP",
    -1.5,
    lo=-3.0,
    hi=-0.1,
)
AUDIO_PREP_LOUDNORM_LRA: float = _whisper_float_env(
    "MEETING_ASSISTANT_AUDIO_PREP_LOUDNORM_LRA",
    11.0,
    lo=1.0,
    hi=20.0,
)


def _parse_whisper_compute_type_chain(raw: str) -> tuple[str, ...] | None:
    if not raw.strip():
        return None
    parts: list[str] = []
    for x in raw.split(","):
        t = x.strip().lower()
        if t and t not in parts:
            parts.append(t)
    return tuple(parts) if parts else None


def whisper_compute_type_candidates_for_device(device: str) -> tuple[str, ...]:
    """CTranslate2 compute types to try for WhisperX ASR load, in order.

    Defaults: GPU (``cuda``) → float16, int16, int8, default.
    CPU → int16, int8, default.

    Override for the active load with ``MEETING_ASSISTANT_WHISPER_COMPUTE_TYPES`` (comma-separated).
    """
    override = _parse_whisper_compute_type_chain(
        os.environ.get("MEETING_ASSISTANT_WHISPER_COMPUTE_TYPES", "")
    )
    if override is not None:
        return override
    if device.strip().lower() == "cuda":
        return ("float16", "int16", "int8", "default")
    return ("int16", "int8", "default")


# Minimum model.bin size (bytes) for cache to count as complete. Override with
# MEETING_ASSISTANT_WHISPER_MIN_BIN_BYTES for any model (including custom Hub ids).
WHISPER_MODEL_BIN_MIN_BYTES: dict[str, int] = {
    "tiny.en": 70_000_000,
    "tiny": 70_000_000,
    "base.en": 130_000_000,
    "base": 130_000_000,
    "small.en": 450_000_000,
    "small": 450_000_000,
    "medium.en": 1_400_000_000,
    "medium": 1_400_000_000,
    "large-v1": 2_400_000_000,
    "large-v2": 2_400_000_000,
    "large-v3": 2_600_000_000,
    "large": 2_600_000_000,
    "distil-large-v2": 750_000_000,
    "distil-medium.en": 350_000_000,
    "distil-small.en": 90_000_000,
    "distil-large-v3": 950_000_000,
    "distil-large-v3.5": 950_000_000,
    "large-v3-turbo": 1_400_000_000,
    "turbo": 1_400_000_000,
}


def whisper_model_bin_min_bytes() -> int:
    """Lower bound for CT2 ``model.bin`` size for the configured model."""
    override = os.environ.get("MEETING_ASSISTANT_WHISPER_MIN_BIN_BYTES", "").strip()
    if override:
        return int(override)
    key = WHISPER_MODEL_SIZE.strip()
    if "/" in key:
        return 500_000_000
    return WHISPER_MODEL_BIN_MIN_BYTES.get(key, 500_000_000)


def whisper_hf_repo_id() -> str:
    """Hugging Face repo id for the configured WhisperX ASR (CTranslate2) model size."""
    key = WHISPER_MODEL_SIZE.strip()
    if "/" in key:
        return key
    repo = FASTER_WHISPER_HF_REPOS.get(key)
    if repo is None:
        raise ValueError(
            f"Unknown MEETING_ASSISTANT_WHISPER_MODEL={key!r}; "
            f"use a known size or a full org/name repo id."
        )
    return repo


MOCK_PIPELINE_DELAY_SEC: float = float(os.environ.get("MEETING_ASSISTANT_MOCK_DELAY", "0.45"))


def _local_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "MeetingAssistant"
    return Path.home() / ".local" / "share" / "MeetingAssistant"


DATA_DIR: Path = Path(os.environ.get("MEETING_ASSISTANT_DATA_DIR", str(_local_data_dir())))
DB_PATH: Path = Path(os.environ.get("MEETING_ASSISTANT_DB", str(DATA_DIR / "meetings.db")))

# Audio / transcript / summary files: see services.output_paths.resolve_meeting_output_dirs
DEFAULT_MEETING_OUTPUT_ROOT: Path = PROJECT_ROOT / "meeting_outputs"
