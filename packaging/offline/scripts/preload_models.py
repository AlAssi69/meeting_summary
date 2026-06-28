"""Preload Whisper/HF assets at image build time for offline inference containers.

Standalone by design: this script must NOT import the ``meeting_assistant`` package so
that the Docker layer running it stays cached across application source changes. It is
driven purely by environment variables / build-args:

- ``MEETING_ASSISTANT_WHISPER_MODEL`` (default ``large-v3-turbo``): a known faster-whisper
  size key (resolved via the embedded map below) or a full ``org/name`` Hugging Face repo id.
- ``MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE`` (default ``ar``): ISO-639-1 code for the
  WhisperX forced-alignment model to seed into the HF cache.
- ``MEETING_ASSISTANT_WHISPER_CACHE``: CT2 Whisper download root (faster-whisper layout).
- ``HF_HOME``: Hugging Face cache root for alignment / tokenizer assets.
- ``HF_TOKEN`` / ``HF_ACCESS_TOKEN`` / ``HUGGING_FACE_HUB_TOKEN``: optional Hub token for
  faster downloads and higher rate limits during the **build** (not baked into runtime ENV).

The CT2 ``allow_patterns`` here MUST stay aligned with
``src/meeting_assistant/services/whisper_hub_download.py`` and ``faster_whisper.utils.download_model``.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from huggingface_hub import HfApi, hf_hub_download, snapshot_download

T = TypeVar("T")

# Mirror of meeting_assistant.config.FASTER_WHISPER_HF_REPOS. Kept here (duplicated on
# purpose) so this preload layer does not depend on the application source tree.
_FASTER_WHISPER_HF_REPOS: dict[str, str] = {
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

# Must stay aligned with faster_whisper.utils.download_model (same allow_patterns).
_CT2_ALLOW_PATTERNS: list[str] = [
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
]

# Typical model.bin sizes (bytes) for user-facing progress hints.
_MODEL_BIN_HINT_BYTES: dict[str, int] = {
    "large-v3-turbo": 1_400_000_000,
    "turbo": 1_400_000_000,
    "large-v3": 2_600_000_000,
    "large": 2_600_000_000,
}


def _log(msg: str) -> None:
    print(msg, flush=True)


def _hf_token() -> str | None:
    for key in ("HF_TOKEN", "HF_ACCESS_TOKEN", "HUGGING_FACE_HUB_TOKEN", "MEETING_ASSISTANT_HF_TOKEN"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    return None


def _whisper_model_size() -> str:
    return (os.environ.get("MEETING_ASSISTANT_WHISPER_MODEL") or "large-v3-turbo").strip()


def _whisper_hf_repo_id(model_size: str) -> str:
    if "/" in model_size:
        return model_size
    repo = _FASTER_WHISPER_HF_REPOS.get(model_size)
    if repo is None:
        raise ValueError(
            f"Unknown MEETING_ASSISTANT_WHISPER_MODEL={model_size!r}; "
            f"use a known size or a full org/name repo id."
        )
    return repo


def _whisper_cache_dir() -> Path:
    raw = os.environ.get("MEETING_ASSISTANT_WHISPER_CACHE")
    if raw:
        return Path(raw)
    return Path("/opt/meeting-assistant/models/whisper")


def _hf_cache_dir() -> Path:
    raw = os.environ.get("HF_HOME")
    if raw:
        return Path(raw)
    return Path("/opt/meeting-assistant/models/hf")


def _align_language() -> str:
    return (os.environ.get("MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE") or "ar").strip().lower()


def _retry(
    label: str,
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay_sec: float = 5.0,
) -> T:
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            delay = base_delay_sec * attempt
            _log(f"[preload] {label} failed (attempt {attempt}/{attempts}): {exc}")
            _log(f"[preload] Retrying in {delay:.0f}s...")
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def _match_repo_files(repo_id: str, patterns: list[str], token: str | None) -> list[str]:
    api = HfApi(token=token)
    all_files = api.list_repo_files(repo_id, repo_type="model")
    matched: list[str] = []
    for pattern in patterns:
        matched.extend(f for f in all_files if fnmatch.fnmatch(f, pattern))
    # Small files first; model.bin last (largest, slowest).
    unique = sorted(set(matched), key=lambda name: (name == "model.bin", name))
    if not unique:
        raise RuntimeError(f"No files matched {patterns!r} in repo {repo_id}")
    return unique


def _format_size_hint(num_bytes: int | None) -> str:
    if num_bytes is None or num_bytes <= 0:
        return "unknown size"
    if num_bytes >= 1_000_000_000:
        return f"~{num_bytes / 1_000_000_000:.1f} GB"
    if num_bytes >= 1_000_000:
        return f"~{num_bytes / 1_000_000:.0f} MB"
    return f"~{num_bytes / 1_000:.0f} KB"


def init_hf_cache() -> None:
    hf_home = _hf_cache_dir()
    hf_home.mkdir(parents=True, exist_ok=True)
    token = _hf_token()
    _log(f"[preload] Initializing HF cache at {hf_home}...")
    snapshot_download(
        repo_id="hf-internal-testing/tiny-random-bert",
        allow_patterns=["config.json"],
        local_files_only=False,
        cache_dir=str(hf_home),
        token=token,
    )
    _log(f"[preload] HF cache ready: {hf_home}")


def seed_whisper_ct2() -> None:
    model_size = _whisper_model_size()
    repo = _whisper_hf_repo_id(model_size)
    target = _whisper_cache_dir()
    target.mkdir(parents=True, exist_ok=True)
    token = _hf_token()

    if token:
        _log("[preload] HF token present (authenticated Hub download).")
    else:
        _log(
            "[preload] No HF token set. Downloads work but may be slower or stall under "
            "rate limits. Set HF_TOKEN in the environment before docker build."
        )

    transfer = (os.environ.get("HF_HUB_ENABLE_HF_TRANSFER") or "").strip().lower()
    if transfer in ("1", "true", "yes", "on"):
        _log("[preload] HF transfer acceleration enabled (hf_transfer).")

    files = _match_repo_files(repo, _CT2_ALLOW_PATTERNS, token)
    _log(f"[preload] Whisper CT2 model={model_size} repo={repo}")
    _log(f"[preload] Files to download ({len(files)}): {', '.join(files)}")

    api = HfApi(token=token)
    last_path = ""
    for index, filename in enumerate(files, start=1):
        size_hint = ""
        if filename == "model.bin":
            size_hint = _format_size_hint(_MODEL_BIN_HINT_BYTES.get(model_size, 1_400_000_000))
            _log(
                f"[preload] ({index}/{len(files)}) Downloading {filename} ({size_hint}) — "
                "this is the slow step; network may look idle between progress updates."
            )
        else:
            try:
                info = api.get_paths_info(repo, [filename], repo_type="model")[0]
                size_hint = _format_size_hint(getattr(info, "size", None))
            except Exception:
                size_hint = "unknown size"
            _log(f"[preload] ({index}/{len(files)}) Downloading {filename} ({size_hint})...")

        t0 = time.perf_counter()

        def _download_one(name: str = filename) -> str:
            return hf_hub_download(
                repo_id=repo,
                filename=name,
                repo_type="model",
                cache_dir=str(target),
                local_files_only=False,
                token=token,
                resume_download=True,
            )

        last_path = _retry(f"download {filename}", _download_one)
        elapsed = time.perf_counter() - t0
        _log(f"[preload]   done {filename} in {elapsed:.1f}s -> {last_path}")

    _log(f"[preload] Whisper cache ready: {last_path}")


def seed_alignment_model() -> None:
    lang = _align_language()
    _log(f"[preload] Downloading alignment model for language={lang}...")
    import whisperx

    model_a, metadata = whisperx.load_align_model(language_code=lang, device="cpu")
    _ = (model_a, metadata)
    _log(f"[preload] Alignment artifacts in HF cache: {_hf_cache_dir()}")


def _run_stage(stage: str) -> None:
    t0 = time.perf_counter()
    _log(f"[preload] Stage start: {stage}")
    if stage in ("all", "whisper"):
        init_hf_cache()
        seed_whisper_ct2()
    if stage in ("all", "align"):
        seed_alignment_model()
    elapsed = time.perf_counter() - t0
    _log(f"[preload] Stage done: {stage} ({elapsed:.1f}s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preload offline inference models.")
    parser.add_argument(
        "--stage",
        choices=("all", "whisper", "align"),
        default="all",
        help="whisper = HF cache + CT2 Whisper download (needs only huggingface_hub); "
        "align = WhisperX alignment model (needs torch/whisperx); all = both.",
    )
    args = parser.parse_args()
    _run_stage(args.stage)
