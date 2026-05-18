from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from meeting_assistant import config
from meeting_assistant.services.whisper_hub_download import download_faster_whisper_ct2
from meeting_assistant.trace import trace_step

_log = logging.getLogger(__name__)


class ModelDownloadWorker(QThread):
    """Downloads the configured faster-whisper CT2 snapshot off the GUI thread."""

    # Use float for byte counts: Qt meta-type ``int`` is 32-bit; model.bin total exceeds 2^31-1.
    progress = Signal(float, float, float, str)
    finished_ok = Signal()
    failed = Signal(str)

    def run(self) -> None:
        try:
            repo = config.whisper_hf_repo_id()
            trace_step(
                "ModelDownloadWorker starting repo=%s dest=%s",
                repo,
                config.WHISPER_DOWNLOAD_ROOT,
            )

            def _cb(n: int, total: int | None, rate: float, desc: str) -> None:
                t = -1.0 if total is None else float(total)
                self.progress.emit(float(n), t, float(rate), desc)

            download_faster_whisper_ct2(
                repo,
                config.WHISPER_DOWNLOAD_ROOT,
                progress=_cb,
            )
            trace_step("ModelDownloadWorker finished_ok repo=%s", repo)
            self.finished_ok.emit()
        except Exception as e:
            _log.exception("Model download failed")
            self.failed.emit(str(e))
