from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from meeting_assistant import config
from meeting_assistant.ports.summarization import SummarizationPort
from meeting_assistant.workers.thread_interrupt import interruptible_sleep_sec

_log = logging.getLogger(__name__)


class SummarizeWorker(QThread):
    """Runs summarization only off the GUI thread."""

    completed = Signal(str)
    failed = Signal(str)
    interrupted = Signal()

    def __init__(
        self,
        transcript: str,
        system_prompt: str,
        summarization: SummarizationPort,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._transcript = transcript
        self._system_prompt = system_prompt
        self._summarization = summarization

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                self.interrupted.emit()
                return
            if config.USE_MOCK_BACKEND and interruptible_sleep_sec(
                self, config.MOCK_PIPELINE_DELAY_SEC
            ):
                self.interrupted.emit()
                return
            if self.isInterruptionRequested():
                self.interrupted.emit()
                return
            summary = self._summarization.summarize(self._transcript, self._system_prompt)
            if self.isInterruptionRequested():
                self.interrupted.emit()
                return
            self.completed.emit(summary)
        except Exception as e:
            _log.exception("Summarize-only failed")
            self.failed.emit(str(e))
