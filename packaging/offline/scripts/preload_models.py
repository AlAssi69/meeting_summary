"""Preload Whisper/HF assets at image build time for offline inference containers."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow `python packaging/offline/scripts/preload_models.py` from repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from huggingface_hub import snapshot_download

from meeting_assistant import config
from meeting_assistant.services.whisper_hub_download import download_faster_whisper_ct2


def _hf_cache() -> str:
    return str(Path(os.environ.get("HF_HOME", str(config.PROJECT_ROOT / "models" / "hf"))))


def seed_whisper_ct2() -> None:
    repo = config.whisper_hf_repo_id()
    print(f"[preload] Whisper CT2 repo: {repo}")
    target = Path(config.WHISPER_DOWNLOAD_ROOT)
    target.mkdir(parents=True, exist_ok=True)
    download_faster_whisper_ct2(repo, target)
    print(f"[preload] Whisper cache ready: {target}")


def seed_alignment_model() -> None:
    lang = (config.WHISPER_ALIGN_LANGUAGE or "ar").strip().lower()
    print(f"[preload] Alignment language: {lang}")
    import whisperx

    model_a, metadata = whisperx.load_align_model(language_code=lang, device="cpu")
    _ = (model_a, metadata)
    print(f"[preload] Alignment artifacts in HF cache: {_hf_cache()}")


def init_hf_cache() -> None:
    hf_home = Path(_hf_cache())
    hf_home.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id="hf-internal-testing/tiny-random-bert",
        allow_patterns=["config.json"],
        local_files_only=False,
        cache_dir=str(hf_home),
    )
    print(f"[preload] HF cache initialized: {hf_home}")


if __name__ == "__main__":
    init_hf_cache()
    seed_whisper_ct2()
    seed_alignment_model()
    print("[preload] Done.")
