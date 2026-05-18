"""Verify local faster-whisper CT2 cache is complete (no false positives on partial downloads)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from huggingface_hub.file_download import repo_folder_name

from meeting_assistant import config

_log = logging.getLogger(__name__)


def _hub_repo_root(cache_dir: Path, repo_id: str) -> Path:
    name = repo_folder_name(repo_id=repo_id, repo_type="model")
    return cache_dir / name


def _has_incomplete_files(root: Path) -> bool:
    if not root.is_dir():
        return False
    try:
        for p in root.rglob("*"):
            if p.is_file() and p.name.endswith(".incomplete"):
                return True
    except OSError as e:
        _log.debug("Incomplete scan failed under %s: %s", root, e)
    return False


def _resolve_snapshot_dir() -> Path | None:
    try:
        from faster_whisper.utils import download_model

        path = download_model(
            config.WHISPER_MODEL_SIZE,
            local_files_only=True,
            cache_dir=str(config.WHISPER_DOWNLOAD_ROOT),
        )
        return Path(path) if path else None
    except Exception as e:
        _log.debug("No local snapshot yet: %s", e)
        return None


def _verify_snapshot_contents(snapshot: Path, min_model_bin: int) -> bool:
    if not snapshot.is_dir():
        return False
    required = ["model.bin", "config.json", "tokenizer.json", "preprocessor_config.json"]
    for name in required:
        if not (snapshot / name).is_file():
            return False
    voc = list(snapshot.glob("vocabulary.*"))
    if not voc:
        return False
    bin_path = snapshot / "model.bin"
    try:
        size = bin_path.stat().st_size
    except OSError:
        return False
    if size < min_model_bin:
        _log.debug(
            "model.bin too small (%s < %s bytes)", size, min_model_bin
        )
        return False
    return True


def is_whisper_ct2_cache_complete() -> bool:
    """True only when Hub snapshot exists, required files + model.bin size look complete, no .incomplete."""
    if config.USE_MOCK_BACKEND:
        return True
    snap = _resolve_snapshot_dir()
    if snap is None:
        return False
    min_b = config.whisper_model_bin_min_bytes()
    if not _verify_snapshot_contents(snap, min_b):
        return False
    try:
        repo_id = config.whisper_hf_repo_id()
    except ValueError:
        return False
    hub_root = _hub_repo_root(config.WHISPER_DOWNLOAD_ROOT, repo_id)
    if _has_incomplete_files(hub_root):
        _log.debug("Hub cache has .incomplete files under %s", hub_root)
        return False
    return True


def clear_whisper_hub_repo_cache() -> None:
    """Remove the Hugging Face hub folder for the configured repo under WHISPER_DOWNLOAD_ROOT."""
    repo_id = config.whisper_hf_repo_id()
    folder = _hub_repo_root(config.WHISPER_DOWNLOAD_ROOT, repo_id)
    if folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)
        _log.info("Removed Whisper hub cache folder %s", folder)


def whisper_cache_status_hint() -> str:
    """Short user-facing line when the model is not ready (empty when ready or mock)."""
    case = whisper_cache_ui_case()
    if case == "none":
        return ""
    if case == "missing":
        return "Model not installed. Use Download to fetch Whisper weights (~several GB for large-v3)."
    return (
        "Download incomplete or cache is damaged — press Download to resume, "
        "or remove cached files to start over."
    )


def whisper_cache_ui_case() -> str:
    """Machine-readable hint for UI translation: none | missing | damaged."""
    if config.USE_MOCK_BACKEND:
        return "none"
    if is_whisper_ct2_cache_complete():
        return "none"
    if _resolve_snapshot_dir() is None:
        return "missing"
    return "damaged"
