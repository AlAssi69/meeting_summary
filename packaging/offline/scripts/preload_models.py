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

The CT2 ``allow_patterns`` here MUST stay aligned with
``src/meeting_assistant/services/whisper_hub_download.py`` and ``faster_whisper.utils.download_model``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from huggingface_hub import snapshot_download

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


def init_hf_cache() -> None:
    hf_home = _hf_cache_dir()
    hf_home.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id="hf-internal-testing/tiny-random-bert",
        allow_patterns=["config.json"],
        local_files_only=False,
        cache_dir=str(hf_home),
    )
    print(f"[preload] HF cache initialized: {hf_home}")


def seed_whisper_ct2() -> None:
    model_size = _whisper_model_size()
    repo = _whisper_hf_repo_id(model_size)
    target = _whisper_cache_dir()
    target.mkdir(parents=True, exist_ok=True)
    print(f"[preload] Whisper CT2 model={model_size} repo={repo}")
    path = snapshot_download(
        repo,
        repo_type="model",
        cache_dir=str(target),
        local_files_only=False,
        allow_patterns=_CT2_ALLOW_PATTERNS,
    )
    print(f"[preload] Whisper cache ready: {path}")


def seed_alignment_model() -> None:
    lang = _align_language()
    print(f"[preload] Alignment language: {lang}")
    import whisperx

    model_a, metadata = whisperx.load_align_model(language_code=lang, device="cpu")
    _ = (model_a, metadata)
    print(f"[preload] Alignment artifacts in HF cache: {_hf_cache_dir()}")


def _run_stage(stage: str) -> None:
    # Stages exist so the Dockerfile can download the large Whisper CT2 model in a layer that
    # depends ONLY on huggingface_hub (cheap to install) — the heavy torch/whisperx install
    # happens between the "whisper" and "align" stages. Editing torch/whisperx requirements
    # therefore does NOT re-download the big Whisper model.
    if stage in ("all", "whisper"):
        init_hf_cache()
        seed_whisper_ct2()
    if stage in ("all", "align"):
        seed_alignment_model()
    print(f"[preload] Done (stage={stage}).")


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
