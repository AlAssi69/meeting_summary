"""Preload Whisper/HF assets so runtime can stay offline."""

from __future__ import annotations

import os
from pathlib import Path

from huggingface_hub import snapshot_download

from meeting_assistant import config
from meeting_assistant.services.whisper_hub_download import download_faster_whisper_ct2


def _hf_cache() -> str:
    return str(Path(os.environ.get("HF_HOME", str(config.PROJECT_ROOT / "models" / "hf"))))


def seed_whisper_ct2() -> None:
    repo = config.whisper_hf_repo_id()
    print(f"[seed] Downloading Whisper CT2 repo: {repo}")
    target = Path(config.WHISPER_DOWNLOAD_ROOT)
    target.mkdir(parents=True, exist_ok=True)
    download_faster_whisper_ct2(repo, target)
    print(f"[seed] Whisper cache ready: {target}")


def seed_alignment_model() -> None:
    # Default aligns with project config (Arabic), but can be overridden by env.
    lang = (config.WHISPER_ALIGN_LANGUAGE or "ar").strip().lower()
    print(f"[seed] Preloading alignment model language: {lang}")

    # WhisperX internally uses the HF hub; this call usually fetches the required files.
    import whisperx

    model_a, metadata = whisperx.load_align_model(language_code=lang, device="cpu")
    _ = (model_a, metadata)
    print(f"[seed] Alignment artifacts ready in HF cache: {_hf_cache()}")


def seed_diarization_optional() -> None:
    enabled = os.environ.get("SEED_DIARIZATION", "0").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        print("[seed] Skipping diarization preload (SEED_DIARIZATION!=1).")
        return

    token = (
        os.environ.get("MEETING_ASSISTANT_HF_TOKEN")
        or os.environ.get("HF_ACCESS_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        or os.environ.get("HF_TOKEN")
    )
    if not token:
        raise RuntimeError("SEED_DIARIZATION=1 requires a Hugging Face token in env.")

    # WhisperX version-dependent pyannote identifiers; use default API path.
    print("[seed] Preloading diarization pipeline assets...")
    from whisperx.diarize import DiarizationPipeline

    pipeline = DiarizationPipeline(token=token, device="cpu")
    _ = pipeline
    print("[seed] Diarization artifacts are cached.")


def preseed_hf_home_hint() -> None:
    hf_home = Path(_hf_cache())
    hf_home.mkdir(parents=True, exist_ok=True)
    # Ensure cache path exists even before first download.
    snapshot_download(
        repo_id="hf-internal-testing/tiny-random-bert",
        allow_patterns=["config.json"],
        local_files_only=False,
        cache_dir=str(hf_home),
    )
    print(f"[seed] HF cache initialized: {hf_home}")


if __name__ == "__main__":
    preseed_hf_home_hint()
    seed_whisper_ct2()
    seed_alignment_model()
    seed_diarization_optional()
    print("[seed] Done.")
