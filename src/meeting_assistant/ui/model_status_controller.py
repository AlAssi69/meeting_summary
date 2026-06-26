from __future__ import annotations

import logging

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from meeting_assistant import config
from meeting_assistant.ports.speech_model_status import SpeechModelStatusSource
from meeting_assistant.services.whisper_cache_integrity import (
    clear_whisper_hub_repo_cache,
    whisper_cache_ui_case,
)
from meeting_assistant.workers.model_download_worker import ModelDownloadWorker

_log = logging.getLogger(__name__)


class ModelStatusController(QObject):
    """QML-facing speech model cache state and on-demand download."""

    modelReadyChanged = Signal()
    downloadingChanged = Signal()
    downloadErrorChanged = Signal()
    progressFractionChanged = Signal()
    bytesDownloadedChanged = Signal()
    totalDownloadBytesChanged = Signal()
    throughputTextChanged = Signal()
    etaSecondsChanged = Signal()
    progressDetailChanged = Signal()
    cacheStatusHintChanged = Signal()
    progressTotalKnownChanged = Signal()
    progressPercentTextChanged = Signal()
    etaTextChanged = Signal()
    downloadPhaseTextChanged = Signal()
    modelSummaryChanged = Signal()
    hfTokenConfiguredChanged = Signal()
    lastSpeechFailureKindChanged = Signal()

    def __init__(self, engine: SpeechModelStatusSource, parent=None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._model_ready = config.USE_MOCK_BACKEND
        self._downloading = False
        self._download_error = ""
        self._bytes = 0
        self._total = -1
        self._rate = 0.0
        self._desc = ""
        self._worker: ModelDownloadWorker | None = None
        QTimer.singleShot(0, self.refresh)

    def _fmt_bytes(self, n: int) -> str:
        if n < 1024:
            return self.tr("{0} B").format(n)
        if n < 1024 * 1024:
            return self.tr("{0:.1f} KB").format(n / 1024)
        if n < 1024**3:
            return self.tr("{0:.1f} MB").format(n / 1024 / 1024)
        return self.tr("{0:.2f} GB").format(n / 1024**3)

    def _fmt_speed(self, rate: float, n: int, total: int) -> str:
        if rate <= 0:
            return self.tr("—")
        if total > 0 and n <= total and total < 50_000:
            return self.tr("{0:.1f} steps/s").format(rate)
        if rate >= 256:
            return self.tr("{0:.1f} MB/s").format(rate / 1024 / 1024)
        return self.tr("{0:.1f} KB/s").format(rate / 1024)

    def _fmt_eta(self, seconds: float) -> str:
        if seconds < 0 or seconds > 86400 * 7:
            return self.tr("—")
        s = int(round(seconds))
        if s < 60:
            return self.tr("{0}s").format(s)
        m, s = divmod(s, 60)
        if m < 60:
            return self.tr("{0}m {1}s").format(m, s)
        h, m = divmod(m, 60)
        return self.tr("{0}h {1}m").format(h, m)

    @Property(bool, notify=modelReadyChanged)
    def modelReady(self) -> bool:
        return self._model_ready

    @Property(bool, notify=downloadingChanged)
    def downloading(self) -> bool:
        return self._downloading

    @Property(str, notify=downloadErrorChanged)
    def downloadError(self) -> str:
        return self._download_error

    @Property(str, notify=cacheStatusHintChanged)
    def cacheStatusHint(self) -> str:
        parts: list[str] = []
        if not config.USE_MOCK_BACKEND:
            fn = getattr(self._engine, "is_diarization_enabled", None)
            diarization_on = fn() if callable(fn) else True
            hf_fn = getattr(self._engine, "is_hf_token_configured", None)
            if diarization_on and callable(hf_fn) and not hf_fn():
                parts.append(
                    self.tr(
                        "No Hugging Face token — add it in Settings (or set MEETING_ASSISTANT_HF_TOKEN) for "
                        "speaker diarization (accept pyannote model conditions on huggingface.co first)."
                    )
                )
        if config.USE_MOCK_BACKEND or self.offlineBundle:
            pass
        elif self._model_ready:
            pass
        else:
            case = whisper_cache_ui_case()
            if case == "missing":
                parts.append(
                    self.tr(
                        "Model not installed. Use Download to fetch Whisper weights (~several GB for large-v3)."
                    )
                )
            elif case != "none":
                parts.append(
                    self.tr(
                        "Download incomplete or cache is damaged — press Download to resume, "
                        "or remove cached files to start over."
                    )
                )
        return "\n\n".join(parts).strip()

    @Property(bool, notify=progressTotalKnownChanged)
    def progressTotalKnown(self) -> bool:
        return self._total > 0

    @Property(str, notify=progressPercentTextChanged)
    def progressPercentText(self) -> str:
        if not self._downloading:
            return ""
        if self._total <= 0:
            return self.tr("…")
        pct = 100.0 * max(0.0, min(1.0, self._bytes / float(self._total)))
        return self.tr("{0:.0f}%").format(pct)

    @Property(str, notify=etaTextChanged)
    def etaText(self) -> str:
        if not self._downloading:
            return ""
        eta = self.etaSeconds
        if eta < 0:
            return self.tr("—")
        return self._fmt_eta(eta)

    @Property(str, notify=downloadPhaseTextChanged)
    def downloadPhaseText(self) -> str:
        if not self._downloading:
            return ""
        d = (self._desc or "").strip()
        if len(d) > 120:
            return d[:117] + "\u2026"
        return d

    @Property(float, notify=progressFractionChanged)
    def progressFraction(self) -> float:
        if self._total > 0:
            return max(0.0, min(1.0, self._bytes / float(self._total)))
        return 0.0

    @Property(float, notify=bytesDownloadedChanged)
    def bytesDownloaded(self) -> float:
        return float(self._bytes)

    @Property(float, notify=totalDownloadBytesChanged)
    def totalDownloadBytes(self) -> float:
        return float(self._total)

    @Property(str, notify=throughputTextChanged)
    def throughputText(self) -> str:
        return self._fmt_speed(self._rate, self._bytes, self._total)

    @Property(float, notify=etaSecondsChanged)
    def etaSeconds(self) -> float:
        if self._total <= 0 or self._rate <= 0 or self._bytes >= self._total:
            return -1.0
        remain = float(self._total - self._bytes)
        return remain / self._rate if self._rate > 0 else -1.0

    @Property(str, notify=progressDetailChanged)
    def progressDetail(self) -> str:
        if not self._downloading and not self._download_error:
            return ""
        if self._total > 0:
            return self.tr("{0} / {1}").format(
                self._fmt_bytes(self._bytes),
                self._fmt_bytes(self._total),
            )
        if self._bytes > 0:
            return self.tr("{0} downloaded").format(self._fmt_bytes(self._bytes))
        return (self._desc or "").strip() or self.tr("Starting…")

    @Property(str, notify=modelSummaryChanged)
    def modelSummary(self) -> str:
        lang = config.WHISPER_LANGUAGE or "auto"
        base = self.tr("WhisperX · {0} · language={1}").format(config.WHISPER_MODEL_SIZE, lang)
        align = config.WHISPER_ALIGN_LANGUAGE
        if align:
            return base + self.tr(" · align={0}").format(align)
        return base

    @Property(bool, notify=hfTokenConfiguredChanged)
    def hfTokenConfigured(self) -> bool:
        if config.USE_MOCK_BACKEND:
            return True
        fn = getattr(self._engine, "is_hf_token_configured", None)
        return bool(fn()) if callable(fn) else True

    @Property(str, notify=lastSpeechFailureKindChanged)
    def lastSpeechFailureKind(self) -> str:
        if config.USE_MOCK_BACKEND:
            return ""
        raw = getattr(self._engine, "last_failure_kind", "")
        return raw if isinstance(raw, str) else ""

    @Property(str, constant=True)
    def cachePath(self) -> str:
        return str(config.WHISPER_DOWNLOAD_ROOT)

    @Property(bool, constant=True)
    def mockBackend(self) -> bool:
        return bool(config.USE_MOCK_BACKEND)

    @Property(bool, constant=True)
    def offlineBundle(self) -> bool:
        return bool(config.OFFLINE_BUNDLE or config.WHISPER_API_URL)

    @Property(bool, constant=True)
    def remoteWhisperApi(self) -> bool:
        return bool(config.WHISPER_API_URL)

    def _set_ready(self, v: bool) -> None:
        if self._model_ready != v:
            self._model_ready = v
            self.modelReadyChanged.emit()

    def _set_downloading(self, v: bool) -> None:
        if self._downloading != v:
            self._downloading = v
            self.downloadingChanged.emit()

    def _emit_progress_props(self) -> None:
        self.progressFractionChanged.emit()
        self.bytesDownloadedChanged.emit()
        self.totalDownloadBytesChanged.emit()
        self.throughputTextChanged.emit()
        self.etaSecondsChanged.emit()
        self.progressDetailChanged.emit()
        self.progressTotalKnownChanged.emit()
        self.progressPercentTextChanged.emit()
        self.etaTextChanged.emit()
        self.downloadPhaseTextChanged.emit()

    def _update_cache_hint(self) -> None:
        self.cacheStatusHintChanged.emit()
        self.hfTokenConfiguredChanged.emit()
        self.lastSpeechFailureKindChanged.emit()

    @Slot()
    def refreshUiLanguage(self) -> None:
        self.cacheStatusHintChanged.emit()
        self.modelSummaryChanged.emit()
        self.hfTokenConfiguredChanged.emit()
        self.lastSpeechFailureKindChanged.emit()
        self.progressPercentTextChanged.emit()
        self.etaTextChanged.emit()
        self.throughputTextChanged.emit()
        self.progressDetailChanged.emit()
        self.downloadPhaseTextChanged.emit()

    @Slot()
    def refresh(self) -> None:
        if config.USE_MOCK_BACKEND:
            self._set_ready(True)
            self._download_error = ""
            self.downloadErrorChanged.emit()
            self._update_cache_hint()
            return
        self._set_ready(self._engine.is_model_present())
        if self._model_ready:
            self._download_error = ""
            self.downloadErrorChanged.emit()
        self._update_cache_hint()

    @Slot()
    def startDownload(self) -> None:
        if config.USE_MOCK_BACKEND or self.offlineBundle:
            return
        if self._downloading:
            return
        if self._worker and self._worker.isRunning():
            return
        self._download_error = ""
        self.downloadErrorChanged.emit()
        self._bytes = 0
        self._total = -1
        self._rate = 0.0
        self._desc = ""
        self._emit_progress_props()
        self._set_downloading(True)
        w = ModelDownloadWorker(self)
        self._worker = w
        w.progress.connect(self._on_progress)
        w.finished_ok.connect(self._on_finished_ok)
        w.failed.connect(self._on_failed)
        w.finished.connect(w.deleteLater)
        w.start()

    @Slot()
    def clearWhisperModelCache(self) -> None:
        if config.USE_MOCK_BACKEND or self.offlineBundle or self._downloading:
            return
        try:
            clear_whisper_hub_repo_cache()
        except OSError as e:
            _log.exception("Failed to clear Whisper cache")
            self._download_error = str(e)
            self.downloadErrorChanged.emit()
            return
        self._engine.invalidate()
        self.refresh()

    def _on_progress(self, n: float, total: float, rate: float, desc: str) -> None:
        self._bytes = max(0, int(n))
        self._total = int(total) if total >= 0.0 else -1
        self._rate = rate
        self._desc = desc
        self._emit_progress_props()

    def _on_finished_ok(self) -> None:
        self._engine.invalidate()
        self._set_downloading(False)
        self._bytes = 0
        self._total = -1
        self._rate = 0.0
        self._desc = ""
        self._emit_progress_props()
        self.refresh()
        self._worker = None

    def _on_failed(self, message: str) -> None:
        _log.error("Download failed: %s", message)
        self._set_downloading(False)
        self._download_error = message
        self.downloadErrorChanged.emit()
        self._emit_progress_props()
        self._worker = None
        self.refresh()

    def is_transcription_ready(self) -> bool:
        return bool(config.USE_MOCK_BACKEND or self._model_ready)
