"""Download faster-whisper CTranslate2 checkpoints with Hugging Face Hub progress.

allow_patterns must stay aligned with faster_whisper.utils.download_model.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download
from tqdm import tqdm

from meeting_assistant.trace import trace_step

_log = logging.getLogger(__name__)

# Must stay aligned with faster_whisper.utils.download_model (same allow_patterns).
_CT2_ALLOW_PATTERNS: list[str] = [
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
]

ProgressCallback = Callable[[int, int | None, float, str], None]


class _ReportingTqdm(tqdm):
    """tqdm that forwards progress to a callback (e.g. bridged to Qt signals)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._on_progress: ProgressCallback | None = kwargs.pop("on_progress", None)
        super().__init__(*args, **kwargs)

    def update(self, n: float = 1) -> bool:
        ret = super().update(n)
        if self._on_progress is not None:
            d = self.format_dict
            n_val = int(d.get("n") or 0)
            total = d.get("total")
            total_i = int(total) if total is not None else None
            rate = float(d.get("rate") or 0.0)
            desc = str(d.get("desc") or "")
            self._on_progress(n_val, total_i, rate, desc)
        return bool(ret)


def _reporting_tqdm_subclass(on_progress: ProgressCallback) -> type[_ReportingTqdm]:
    """Return a tqdm *class* bound to ``on_progress``.

    ``huggingface_hub.snapshot_download`` passes ``tqdm_class`` to ``thread_map``, which
    requires a real class (``.get_lock()``), not a factory function.
    """

    class _BoundReportingTqdm(_ReportingTqdm):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["on_progress"] = on_progress
            super().__init__(*args, **kwargs)

    return _BoundReportingTqdm


def download_faster_whisper_ct2(
    repo_id: str,
    cache_dir: Path | str,
    *,
    revision: str | None = None,
    token: bool | str | None = None,
    progress: ProgressCallback | None = None,
) -> str:
    """Download CT2 Whisper assets into ``cache_dir`` (same layout faster-whisper expects).

    Returns the local snapshot path string from ``snapshot_download``.
    """
    root = Path(cache_dir)
    root.mkdir(parents=True, exist_ok=True)
    trace_step("Whisper CT2 download starting repo_id=%s cache_dir=%s", repo_id, root)

    tqdm_cls: type[_ReportingTqdm] | None = (
        _reporting_tqdm_subclass(progress) if progress is not None else None
    )

    path = snapshot_download(
        repo_id,
        repo_type="model",
        revision=revision,
        cache_dir=str(root),
        local_files_only=False,
        allow_patterns=_CT2_ALLOW_PATTERNS,
        tqdm_class=tqdm_cls,
        token=token,
    )
    trace_step("Whisper CT2 snapshot_download finished path=%s", path)
    _log.info("Whisper CT2 snapshot ready at %s", path)
    return path
