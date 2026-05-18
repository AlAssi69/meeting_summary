from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

_log = logging.getLogger(__name__)

try:
    from PySide6.QtMultimedia import QAudioInput, QMediaCaptureSession, QMediaRecorder

    _HAS_MM = True
except ImportError:
    QAudioInput = Any  # type: ignore[assignment,misc]
    QMediaCaptureSession = Any  # type: ignore[assignment,misc]
    QMediaRecorder = Any  # type: ignore[assignment,misc]
    _HAS_MM = False


class RecordingController(QObject):
    """Captures microphone via Qt Multimedia (when available)."""

    recordingChanged = Signal()
    captureFailed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._recording = False
        self._temp_path: str | None = None
        self._session: QMediaCaptureSession | None = None
        self._recorder: QMediaRecorder | None = None
        if _HAS_MM:
            self._session = QMediaCaptureSession(self)
            audio_in = QAudioInput(self)
            self._recorder = QMediaRecorder(self)
            self._session.setAudioInput(audio_in)
            self._session.setRecorder(self._recorder)

    def _get_recorder(self) -> QMediaRecorder | None:
        return self._recorder

    @Property(bool, notify=recordingChanged)  # type: ignore[misc]
    def recording(self) -> bool:
        return self._recording

    @Slot(str)
    def startRecording(self, output_dir: str) -> None:
        rec = self._get_recorder()
        if rec is None:
            self.captureFailed.emit(self.tr("Qt Multimedia recorder unavailable."))
            return
        raw = (output_dir or "").strip()
        if not raw:
            self.captureFailed.emit(self.tr("Recording folder is not set."))
            return
        out = Path(raw)
        try:
            out.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.captureFailed.emit(self.tr("Cannot create recording folder: {0}").format(e))
            return
        fd, path = tempfile.mkstemp(suffix=".m4a", prefix="mtg_rec_", dir=str(out))
        os.close(fd)
        self._temp_path = path
        url = QUrl.fromLocalFile(path)
        rec.setOutputLocation(url)
        rec.record()
        self._recording = True
        self.recordingChanged.emit()

    @Slot(result=str)
    def stopRecording(self) -> str:
        rec = self._get_recorder()
        if rec is not None and self._recording:
            rec.stop()
        self._recording = False
        self.recordingChanged.emit()
        p = self._temp_path or ""
        self._temp_path = None
        return p
