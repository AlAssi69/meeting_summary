from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QElapsedTimer, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from meeting_assistant import config
from meeting_assistant.core.constants import (
    AUDIO_EXTENSIONS,
    DEFAULT_RECORDING_LLM_INSTRUCTIONS,
    DEFAULT_RECORDING_WHISPER_CONTEXT,
    AssistantContentKind,
    MessageRole,
    MessageSystemKind,
)
from meeting_assistant.core.models import Message
from meeting_assistant.debug_util import debug_notify
from meeting_assistant.ports.session_repository import SessionRepository
from meeting_assistant.ports.summarization import SummarizationPort
from meeting_assistant.ports.transcription import TranscriptionPort
from meeting_assistant.services.output_paths import resolve_meeting_output_dirs
from meeting_assistant.services.pipeline_prep import prepare_pipeline_audio_and_stem
from meeting_assistant.services.prompt_composition import (
    PipelinePromptContext,
    compose_llm_system_prompt,
)
from meeting_assistant.services.prompts import run_prompt_context
from meeting_assistant.services.session_artifact_folder import (
    ensure_repo_session_has_slug,
    resolve_session_meeting_dirs,
)
from meeting_assistant.services.speaker_mapping import (
    apply_speaker_mapping,
    extract_speaker_keys,
    first_time_range_sec_by_speaker,
)
from meeting_assistant.services.transcript_file import (
    build_meeting_artifact_stem,
    resolve_unique_summary_stem_in_dir,
    write_summary_txt,
)
from meeting_assistant.trace import trace_step
from meeting_assistant.ui.recording_controller import RecordingController

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

    _HAS_SPEAKER_SAMPLE_MM = True
except ImportError:
    QAudioOutput = Any  # type: ignore[misc,assignment]
    QMediaPlayer = Any  # type: ignore[misc,assignment]
    _HAS_SPEAKER_SAMPLE_MM = False

from meeting_assistant.workers.summarize_worker import SummarizeWorker
from meeting_assistant.workers.transcription_worker import TranscriptionWorker

_log = logging.getLogger(__name__)

def _message_to_dict(m: Message) -> dict:
    sk = ""
    if m.role == MessageRole.SYSTEM.value:
        if m.system_kind in (
            MessageSystemKind.ERROR.value,
            MessageSystemKind.WARNING.value,
            MessageSystemKind.INFO.value,
        ):
            sk = m.system_kind
        else:
            c = m.content or ""
            sk = (
                MessageSystemKind.ERROR.value
                if c.startswith("Error:")
                else MessageSystemKind.WARNING.value
            )
    assistant_kind = ""
    if m.role == MessageRole.ASSISTANT.value:
        if m.assistant_kind == AssistantContentKind.TRANSCRIPT.value:
            assistant_kind = AssistantContentKind.TRANSCRIPT.value
        elif m.assistant_kind == AssistantContentKind.SUMMARY.value:
            assistant_kind = AssistantContentKind.SUMMARY.value
        elif m.assistant_kind == AssistantContentKind.SPEAKER_MAP.value:
            assistant_kind = AssistantContentKind.SPEAKER_MAP.value
        elif m.assistant_kind:
            assistant_kind = m.assistant_kind
        elif m.file_path and str(m.file_path).strip():
            assistant_kind = AssistantContentKind.TRANSCRIPT.value
        else:
            assistant_kind = AssistantContentKind.SUMMARY.value
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content or "",
        "filePath": m.file_path or "",
        "systemKind": sk,
        "assistantKind": assistant_kind,
        "createdAt": m.created_at or "",
    }


def _paths_equal(a: str, b: Path) -> bool:
    try:
        return Path(a).resolve() == b.resolve()
    except OSError:
        return a == str(b)


def _find_user_message_for_audio(messages: list[Message], audio_path: Path) -> Message | None:
    for m in reversed(messages):
        if m.role != MessageRole.USER.value or not m.file_path:
            continue
        if _paths_equal(m.file_path, audio_path):
            return m
    return None


def _effective_recording_llm(stored: str | None) -> str:
    """Resolve DB value: explicit empty string means no per-recording LLM layer; NULL → app default."""
    if stored == "":
        return ""
    if stored is None:
        return DEFAULT_RECORDING_LLM_INSTRUCTIONS
    return stored.strip()


def _effective_recording_whisper(stored: str | None) -> str:
    """Resolve DB value: explicit empty means no per-recording Whisper bias; NULL → app default."""
    if stored == "":
        return ""
    if stored is None:
        return DEFAULT_RECORDING_WHISPER_CONTEXT
    return stored.strip()


def _find_anchor_user_before_index(messages: list[Message], index: int) -> Message | None:
    for i in range(index - 1, -1, -1):
        m = messages[i]
        if m.role == MessageRole.USER.value and m.file_path:
            return m
    return None


def _is_transcript_message(m: Message) -> bool:
    if m.role != MessageRole.ASSISTANT.value:
        return False
    if m.assistant_kind == AssistantContentKind.TRANSCRIPT.value:
        return True
    if m.assistant_kind == AssistantContentKind.SUMMARY.value:
        return False
    if m.assistant_kind:
        return False
    return bool(m.file_path and str(m.file_path).strip())


def _message_copy_type_label(tr: Callable[[str], str], m: Message) -> str:
    if m.role == MessageRole.USER.value:
        return tr("User")
    if m.role == MessageRole.SYSTEM.value:
        if m.system_kind == MessageSystemKind.WARNING.value:
            return tr("Warning")
        if m.system_kind == MessageSystemKind.INFO.value:
            return tr("Info")
        return tr("Error")
        if m.role == MessageRole.ASSISTANT.value:
            if m.assistant_kind == AssistantContentKind.TRANSCRIPT.value:
                return tr("Transcript")
            if m.assistant_kind == AssistantContentKind.SUMMARY.value:
                return tr("Summary")
            if m.assistant_kind == AssistantContentKind.SPEAKER_MAP.value:
                return tr("Speaker names")
            return tr("Assistant")
    return m.role


class ChatController(QObject):
    """Chat area: messages, pipeline, file open, recording handoff."""

    messagesChanged = Signal()
    statusChanged = Signal()
    busyChanged = Signal()
    currentPhaseChanged = Signal()
    currentSessionIdChanged = Signal()
    sttPipelineLogChanged = Signal()
    pendingAudioPathChanged = Signal()
    audioImportNameFiltersChanged = Signal()
    processingElapsedTextChanged = Signal()
    pipelineGuardsChanged = Signal()
    speakerSampleContextChanged = Signal()

    def __init__(
        self,
        repo: SessionRepository,
        transcription: TranscriptionPort,
        summarization: SummarizationPort,
        transcription_ready: Callable[[], bool] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._repo = repo
        self._transcription = transcription
        self._summarization = summarization
        self._transcription_ready = transcription_ready or (lambda: True)
        self._session_id: str | None = None
        self._messages: list[dict] = []
        self._status_kind: str = "empty"
        self._status_tpl: str = ""
        self._status_args: tuple[str, ...] = ()
        self._status_free: str = ""
        self._busy = False
        self._phase = "idle"
        self._worker: TranscriptionWorker | None = None
        self._pipeline_audio_path: Path | None = None
        self._pipeline_session_id: str | None = None
        self._summarize_worker: SummarizeWorker | None = None
        self._summarize_session_id: str | None = None
        self._intercept_session_id: str | None = None
        self._intercept_raw_transcript: str = ""
        self._intercept_txt_path: str = ""
        self._intercept_transcript_message_id: str = ""
        self._intercept_map_message_id: str = ""
        self._intercept_speaker_keys: list[str] = []
        self._intercept_speaker_time_ranges: dict[str, tuple[float, float]] = {}
        self._intercept_prompt_ctx: PipelinePromptContext | None = None
        self._pending_prompt_ctx: PipelinePromptContext | None = None
        self._recording = RecordingController(self)
        self._recording.captureFailed.connect(self._on_recording_capture_failed)
        self._status_clear_timer = QTimer(self)
        self._status_clear_timer.setSingleShot(True)
        self._status_clear_timer.setInterval(2500)
        self._status_clear_timer.timeout.connect(self._on_status_clear_timer)
        self._stt_pipeline_log: list[dict[str, str]] = []
        self._pending_audio_path: str | None = None
        self._elapsed_timer = QElapsedTimer()
        self._processing_elapsed_text = ""
        self._processing_tick_timer = QTimer(self)
        self._processing_tick_timer.setInterval(250)
        self._processing_tick_timer.timeout.connect(self._on_processing_tick)
        self._speaker_sample_player: QMediaPlayer | None = None
        self._speaker_sample_audio: QAudioOutput | None = None
        self._speaker_sample_stop_timer = QTimer(self)
        self._speaker_sample_stop_timer.setSingleShot(True)
        self._speaker_sample_stop_timer.timeout.connect(self._stop_speaker_sample_playback)

    def _stop_speaker_sample_playback(self) -> None:
        if self._speaker_sample_player is not None:
            self._speaker_sample_player.stop()

    @Property(str, notify=processingElapsedTextChanged)
    def processingElapsedText(self) -> str:
        return self._processing_elapsed_text

    def _format_elapsed_ms(self, ms: int) -> str:
        sec = ms // 1000
        m, s = divmod(sec, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:d}:{m:02d}:{s:02d}"
        return f"{m:d}:{s:02d}"

    def _on_processing_tick(self) -> None:
        if not self._busy:
            self._processing_tick_timer.stop()
            return
        t = self._format_elapsed_ms(self._elapsed_timer.elapsed())
        if t != self._processing_elapsed_text:
            self._processing_elapsed_text = t
            self.processingElapsedTextChanged.emit()

    @Slot()
    def requestStopProcessing(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
        elif self._summarize_worker is not None and self._summarize_worker.isRunning():
            self._summarize_worker.requestInterruption()

    @Slot(str, str)
    def _on_transcription_interrupted(self, transcript: str, transcript_path: str) -> None:
        self._clear_intercept_fields()
        self._status_clear_timer.stop()
        sid = self._pipeline_session_id
        tp = (transcript_path or "").strip()
        tr_text = (transcript or "").strip()
        has_file = bool(tp and Path(tp).is_file())
        if sid and self._repo.get_session(sid) is not None:
            if tr_text and has_file:
                self._repo.add_message(
                    sid,
                    MessageRole.ASSISTANT.value,
                    transcript,
                    tp,
                    assistant_kind=AssistantContentKind.TRANSCRIPT.value,
                )
                self._repo.add_message(
                    sid,
                    MessageRole.SYSTEM.value,
                    self.tr(
                        "Summarization was skipped because you stopped processing."
                    ),
                    None,
                    system_kind=MessageSystemKind.INFO.value,
                )
            else:
                self._repo.add_message(
                    sid,
                    MessageRole.SYSTEM.value,
                    self.tr("Processing was stopped."),
                    None,
                    system_kind=MessageSystemKind.INFO.value,
                )
            self._reload_messages()
        self._set_phase("idle")
        self._set_status_tpl("Processing was stopped.")
        self._finish_pipeline()

    @Slot()
    def _on_summarize_interrupted(self) -> None:
        self._status_clear_timer.stop()
        sid = self._summarize_session_id
        self._summarize_session_id = None
        self._summarize_worker = None
        if sid and self._repo.get_session(sid) is not None:
            self._repo.add_message(
                sid,
                MessageRole.SYSTEM.value,
                self.tr("Summarization was stopped."),
                None,
                system_kind=MessageSystemKind.INFO.value,
            )
            self._reload_messages()
        self._set_phase("idle")
        self._set_busy(False)
        self._set_status_tpl("Processing was stopped.")

    def _clear_pending_audio(self) -> None:
        if self._pending_audio_path is None:
            return
        self._pending_audio_path = None
        self.pendingAudioPathChanged.emit()

    def _on_status_clear_timer(self) -> None:
        if (
            not self._busy
            and self._status_kind == "tpl"
            and self._status_tpl
            in (
                "Done.",
                "Data path copied to clipboard.",
                "Meeting files folder copied to clipboard.",
                "Message copied to clipboard.",
            )
        ):
            self._set_status_empty()

    @Slot()
    def refreshUiLanguage(self) -> None:
        self.statusChanged.emit()
        self.audioImportNameFiltersChanged.emit()

    def _status_display(self) -> str:
        if self._status_kind == "empty":
            return ""
        if self._status_kind == "free":
            return self._status_free
        t = self.tr(self._status_tpl)
        if self._status_args:
            try:
                return t.format(*self._status_args)
            except (KeyError, IndexError, ValueError):
                return t
        return t

    def _set_status_tpl(self, tpl: str, *args: object) -> None:
        self._status_kind = "tpl"
        self._status_tpl = tpl
        self._status_args = tuple(str(x) for x in args)
        self.statusChanged.emit()

    def _set_status_free(self, text: str) -> None:
        self._status_kind = "free"
        self._status_free = text
        self.statusChanged.emit()

    def _set_status_empty(self) -> None:
        self._status_kind = "empty"
        self.statusChanged.emit()

    @Slot(str)
    def _on_recording_capture_failed(self, msg: str) -> None:
        self._set_status_free(msg)

    def attach_session_id(self, session_id: str) -> None:
        self._session_id = session_id or None
        self._clear_pending_audio()
        self._reload_messages()
        self.currentSessionIdChanged.emit()
        self._emit_pipeline_guards_changed()

    @Property(str, notify=pendingAudioPathChanged)
    def pendingAudioPath(self) -> str:
        return self._pending_audio_path or ""

    @Property(list, notify=audioImportNameFiltersChanged)
    def audioImportNameFilters(self) -> list[str]:
        exts = " ".join(f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS))
        return [self.tr("Audio ({0})").format(exts), self.tr("All files (*)")]

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:
        return self._status_display()

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=currentPhaseChanged)
    def currentPhase(self) -> str:
        return self._phase

    @Property(list, notify=messagesChanged)
    def messages(self) -> list:
        return self._messages

    @Property(list, notify=sttPipelineLogChanged)
    def sttPipelineLog(self) -> list:
        return list(self._stt_pipeline_log)

    @Property(QObject, constant=True)
    def recorder(self) -> RecordingController:
        return self._recording

    @Property(str, notify=speakerSampleContextChanged)
    def speakerSampleAudioPath(self) -> str:
        if not self._speaker_map_pending():
            return ""
        p = self._pipeline_audio_path
        if not p:
            return ""
        try:
            if p.is_file():
                return str(p)
        except OSError:
            return ""
        return ""

    @Property(bool, constant=True)
    def speakerSamplePlaybackAvailable(self) -> bool:
        return bool(_HAS_SPEAKER_SAMPLE_MM)

    def _ensure_speaker_sample_player(self) -> tuple[QMediaPlayer, QAudioOutput] | None:
        if not _HAS_SPEAKER_SAMPLE_MM:
            return None
        if self._speaker_sample_player is None:
            ao = QAudioOutput(self)
            pl = QMediaPlayer(self)
            pl.setAudioOutput(ao)
            self._speaker_sample_audio = ao
            self._speaker_sample_player = pl
        assert self._speaker_sample_player is not None
        assert self._speaker_sample_audio is not None
        return self._speaker_sample_player, self._speaker_sample_audio

    @Slot(str)
    def playSpeakerVoiceSample(self, speaker_key: str) -> None:
        if not _HAS_SPEAKER_SAMPLE_MM:
            return
        if not self._speaker_map_pending():
            return
        key = (speaker_key or "").strip()
        if not key:
            return
        ranges = self._intercept_speaker_time_ranges.get(key)
        if ranges is None:
            self._set_status_tpl("No voice sample time range for this speaker.")
            return
        audio_path = self._pipeline_audio_path
        if audio_path is None:
            self._set_status_tpl("Audio file is not available for playback.")
            return
        try:
            if not audio_path.is_file():
                self._set_status_tpl("Audio file is not available for playback.")
                return
        except OSError:
            self._set_status_tpl("Audio file is not available for playback.")
            return
        start_sec, end_sec = ranges
        span = max(0.0, float(end_sec) - float(start_sec))
        play_sec = max(0.2, min(5.0, span if span > 0 else 0.2))
        pair = self._ensure_speaker_sample_player()
        if pair is None:
            return
        pl, _ao = pair
        self._speaker_sample_stop_timer.stop()
        pl.stop()
        pl.setSource(QUrl.fromLocalFile(str(audio_path.resolve())))
        pl.setPosition(int(start_sec * 1000))
        pl.play()
        self._speaker_sample_stop_timer.setInterval(int(play_sec * 1000))
        self._speaker_sample_stop_timer.start()

    def _set_busy(self, b: bool) -> None:
        prev = self._busy
        self._busy = b
        if b:
            self._elapsed_timer.restart()
            self._processing_elapsed_text = self._format_elapsed_ms(0)
            self.processingElapsedTextChanged.emit()
            self._processing_tick_timer.start()
        else:
            self._processing_tick_timer.stop()
            if self._processing_elapsed_text:
                self._processing_elapsed_text = ""
                self.processingElapsedTextChanged.emit()
        if prev != b:
            self.busyChanged.emit()
        self._emit_pipeline_guards_changed()

    def _set_phase(self, p: str) -> None:
        self._phase = p
        self.currentPhaseChanged.emit()
        self._emit_pipeline_guards_changed()

    def _processing_busy(self) -> bool:
        if self._worker is not None and self._worker.isRunning():
            return True
        if self._summarize_worker is not None and self._summarize_worker.isRunning():
            return True
        return False

    def _speaker_map_pending(self) -> bool:
        return self._phase == "awaiting_speaker_map" and bool(
            (self._intercept_session_id or "").strip()
        )

    def _speaker_map_pending_for_viewed_session(self) -> bool:
        return self._speaker_map_pending() and self._intercept_session_id == self._session_id

    def _staging_import_blocked(self) -> bool:
        """Block staging/import on the viewed session while workers run or that session awaits speaker names."""
        return self._processing_busy() or self._speaker_map_pending_for_viewed_session()

    def _pipeline_start_globally_blocked(self) -> bool:
        """Block any new transcription/summarize/reprocess while workers run or any session awaits speaker names."""
        return self._processing_busy() or self._speaker_map_pending()

    def _emit_pipeline_guards_changed(self) -> None:
        self.pipelineGuardsChanged.emit()

    def _pipeline_start_block_user_tpl(self) -> str:
        if self._processing_busy():
            return "Already processing."
        if self._speaker_map_pending():
            if self._intercept_session_id and self._intercept_session_id != self._session_id:
                return (
                    "Finish or cancel speaker naming in another session before starting a new run."
                )
            return "Finish or cancel speaker naming before starting a new run."
        return "Already processing."

    def _staging_import_block_user_tpl(self) -> str:
        if self._processing_busy():
            return "Already processing."
        if self._speaker_map_pending_for_viewed_session():
            return "Finish or cancel speaker naming before importing another file."
        return "Already processing."

    @Property(bool, notify=pipelineGuardsChanged)
    def pipelineStartLocked(self) -> bool:
        return self._pipeline_start_globally_blocked()

    @Property(bool, notify=pipelineGuardsChanged)
    def stagingImportLocked(self) -> bool:
        return self._staging_import_blocked()

    @Property(bool, notify=busyChanged)
    def recordingLocked(self) -> bool:
        return self._busy

    def _clear_stt_pipeline_log(self) -> None:
        if self._stt_pipeline_log:
            self._stt_pipeline_log = []
            self.sttPipelineLogChanged.emit()

    def _append_stt_pipeline_event(self, kind: str, message: str) -> None:
        self._stt_pipeline_log.append({"kind": kind, "message": message})
        if len(self._stt_pipeline_log) > 15:
            self._stt_pipeline_log = self._stt_pipeline_log[-15:]
        self.sttPipelineLogChanged.emit()

    def _reload_messages(self) -> None:
        if not self._session_id:
            self._messages = []
        else:
            self._messages = [
                _message_to_dict(m) for m in self._repo.list_messages(self._session_id)
            ]
        self.messagesChanged.emit()

    @Slot(str)
    def setCurrentSessionId(self, session_id: str) -> None:
        self.attach_session_id(session_id)

    @Slot(str)
    def processAudioFile(self, path: str) -> None:
        """Stages audio for Send (same as stageAudioFile; kept for compatibility)."""
        self.stageAudioFile(path)

    @Slot(str)
    def stageAudioFile(self, path: str) -> None:
        if not self._session_id:
            self._set_status_tpl("No active session.")
            return
        if self._staging_import_blocked():
            self._set_status_tpl(self._staging_import_block_user_tpl())
            return
        if self._recording.recording:
            self._set_status_tpl("Stop recording before importing a file.")
            return
        raw = (path or "").strip()
        if not raw:
            return
        p = Path(raw)
        try:
            p = p.resolve()
        except OSError:
            self._set_status_tpl("Invalid file path.")
            return
        if not p.is_file():
            if p.exists() and p.is_dir():
                self._set_status_tpl("Folders are not supported — choose an audio file: {0}", p.name)
            else:
                self._set_status_tpl("File not found: {0}", p.name)
            return
        ext_str = ", ".join(sorted(AUDIO_EXTENSIONS))
        if p.suffix.lower() not in AUDIO_EXTENSIONS:
            suf = p.suffix.lower() if p.suffix else "(no extension)"
            self._set_status_tpl(
                "Not supported audio ({0}): {1}. Use one of: {2}",
                suf,
                p.name,
                ext_str,
            )
            return
        prev = self._pending_audio_path
        debug_notify(f"Stage audio for send: {p.name}")
        self._set_pending_audio_path(str(p))
        if prev and prev != self._pending_audio_path:
            self._set_status_tpl("Replaced staged file — now: {0}", p.name)
        else:
            self._set_status_tpl("Ready to send — audio file: {0}", p.name)

    def _set_pending_audio_path(self, path_norm: str) -> None:
        """Assign staged file path."""
        self._pending_audio_path = path_norm
        self.pendingAudioPathChanged.emit()

    @Slot(list)
    def stageDroppedLocalPaths(self, paths: list) -> None:
        """Stage one dropped file if it exists and has a supported audio extension."""
        if not self._session_id:
            self._set_status_tpl("No active session.")
            return
        if self._staging_import_blocked():
            self._set_status_tpl(self._staging_import_block_user_tpl())
            return
        if self._recording.recording:
            self._set_status_tpl("Stop recording before importing a file.")
            return
        str_paths = [str(x).strip() for x in paths if x is not None and str(x).strip()]
        if not str_paths:
            self._set_status_tpl("Drop did not contain any file paths.")
            return
        if len(str_paths) > 1:
            self._set_status_tpl("Drop one audio file at a time.")
            return
        raw = str_paths[0]
        try:
            p = Path(raw).resolve()
        except OSError:
            self._set_status_tpl("Could not read dropped file path.")
            return
        if p.is_dir():
            self._set_status_tpl("Folders are not supported — drop an audio file: {0}", p.name)
            return
        if not p.is_file():
            self._set_status_tpl("Not a file or no longer exists: {0}", p.name)
            return
        ext_str = ", ".join(sorted(AUDIO_EXTENSIONS))
        if p.suffix.lower() not in AUDIO_EXTENSIONS:
            suf = p.suffix.lower() if p.suffix else "(no extension)"
            self._set_status_tpl(
                "Not supported audio ({0}): {1}. Use one of: {2}",
                suf,
                p.name,
                ext_str,
            )
            return
        prev = self._pending_audio_path
        debug_notify(f"Stage audio for send: {p.name}")
        self._set_pending_audio_path(str(p))
        if prev and prev != self._pending_audio_path:
            self._set_status_tpl("Replaced staged file — now: {0}", p.name)
        else:
            self._set_status_tpl("Ready to send — audio file: {0}", p.name)

    @Slot()
    def discardPendingAudio(self) -> None:
        if not self._pending_audio_path:
            return
        self._clear_pending_audio()
        self._set_status_tpl("Staged file cleared.")

    def _validate_send_pending_audio(self) -> bool:
        if not self._session_id:
            self._set_status_tpl("No active session.")
            return False
        if self._pipeline_start_globally_blocked():
            self._set_status_tpl(self._pipeline_start_block_user_tpl())
            return False
        if self._recording.recording:
            self._set_status_tpl("Stop recording first, then press Send to run the pipeline.")
            return False
        if not self._pending_audio_path:
            if not self._messages:
                self._set_status_tpl(
                    "Nothing to send yet. Use Record (then Stop recording) or drop an audio file "
                    "on this window, then press Send to set prompts and run the pipeline."
                )
            else:
                self._set_status_tpl(
                    "No audio staged. After you stop recording or drop a file, it appears as ready; "
                    "then press Send to set prompts and run the pipeline."
                )
            return False
        if not config.USE_MOCK_BACKEND and not self._transcription_ready():
            self._set_status_tpl("Speech model missing — open Settings and download Whisper.")
            return False
        p = Path(self._pending_audio_path)
        if not p.is_file():
            self._set_status_tpl("File not found.")
            self._clear_pending_audio()
            return False
        return True

    @Slot(result=bool)
    def sendPendingAudioValidated(self) -> bool:
        return self._validate_send_pending_audio()

    @Slot(str, str)
    def commitSendPendingAudio(self, llm_instructions: str, whisper_context: str) -> None:
        if not self._validate_send_pending_audio():
            return
        p = Path(self._pending_audio_path)
        self._clear_pending_audio()
        debug_notify(f"Queue pipeline for {p.name}")
        llm_s = (llm_instructions or "").strip()
        whisper_s = (whisper_context or "").strip()
        self._start_pipeline(
            p,
            add_user_row=True,
            llm_instructions=llm_s,
            whisper_context=whisper_s,
        )

    @Slot()
    def sendPendingAudio(self) -> None:
        """Run send with default prompts (tests / non-UI callers)."""
        self.commitSendPendingAudio(
            DEFAULT_RECORDING_LLM_INSTRUCTIONS,
            DEFAULT_RECORDING_WHISPER_CONTEXT,
        )

    def _reprocess_audio_validate(self, path: str) -> Path | None:
        if not self._session_id:
            self._set_status_tpl("No active session.")
            return None
        raw = (path or "").strip()
        if not raw:
            return None
        try:
            p = Path(raw).resolve()
        except OSError:
            self._set_status_tpl("Invalid file path.")
            return None
        if not p.is_file():
            self._set_status_tpl("File not found.")
            return None
        if self._pipeline_start_globally_blocked():
            self._set_status_tpl(self._pipeline_start_block_user_tpl())
            return None
        if not config.USE_MOCK_BACKEND and not self._transcription_ready():
            self._set_status_tpl("Speech model missing — open Settings and download Whisper.")
            return None
        return p

    @Slot(str, result=bool)
    def reprocessAudioValidated(self, path: str) -> bool:
        return self._reprocess_audio_validate(path) is not None

    @Slot(str, str, str)
    def commitReprocessAudio(self, path: str, llm_instructions: str, whisper_context: str) -> None:
        p = self._reprocess_audio_validate(path)
        if p is None:
            return
        sid = self._session_id
        if not sid:
            return
        msgs = self._repo.list_messages(sid)
        has_user_audio = any(
            m.role == MessageRole.USER.value
            and m.file_path
            and _paths_equal(m.file_path, p)
            for m in msgs
        )
        debug_notify(f"Reprocess pipeline for {p.name}")
        llm_s = (llm_instructions or "").strip()
        whisper_s = (whisper_context or "").strip()
        self._start_pipeline(
            p,
            add_user_row=not has_user_audio,
            llm_instructions=llm_s,
            whisper_context=whisper_s,
        )

    @Slot(result=str)
    def defaultSendPromptLlm(self) -> str:
        return DEFAULT_RECORDING_LLM_INSTRUCTIONS

    @Slot(result=str)
    def defaultSendPromptWhisper(self) -> str:
        return DEFAULT_RECORDING_WHISPER_CONTEXT

    @Slot(str, result="QVariantMap")
    def reprocessPromptDefaults(self, path: str) -> dict:
        out: dict[str, str] = {
            "llm": DEFAULT_RECORDING_LLM_INSTRUCTIONS,
            "whisper": DEFAULT_RECORDING_WHISPER_CONTEXT,
        }
        sid = self._session_id
        if not sid:
            return out
        raw = (path or "").strip()
        if not raw:
            return out
        try:
            p = Path(raw).resolve()
        except OSError:
            return out
        if not p.is_file():
            return out
        msgs = self._repo.list_messages(sid)
        anchor = _find_user_message_for_audio(msgs, p)
        if anchor is not None:
            out["llm"] = _effective_recording_llm(anchor.recording_llm_instructions)
            out["whisper"] = _effective_recording_whisper(anchor.recording_whisper_context)
        return out

    @Slot(str, result=str)
    def summarizeAgainLlmDefault(self, message_id: str) -> str:
        mid = (message_id or "").strip()
        sid = self._session_id
        if not sid or not mid:
            return DEFAULT_RECORDING_LLM_INSTRUCTIONS
        msgs = self._repo.list_messages(sid)
        idx: int | None = None
        target: Message | None = None
        for i, m in enumerate(msgs):
            if m.id == mid:
                idx = i
                target = m
                break
        if idx is None or target is None or not _is_transcript_message(target):
            return DEFAULT_RECORDING_LLM_INSTRUCTIONS
        anchor = _find_anchor_user_before_index(msgs, idx)
        return _effective_recording_llm(anchor.recording_llm_instructions if anchor else None)

    @Slot(str, result=bool)
    def summarizeAgainValidated(self, message_id: str) -> bool:
        if not self._session_id:
            self._set_status_tpl("No active session.")
            return False
        if self._pipeline_start_globally_blocked():
            self._set_status_tpl(self._pipeline_start_block_user_tpl())
            return False
        sid = self._session_id
        msgs = self._repo.list_messages(sid)
        target: Message | None = None
        for m in msgs:
            if m.id == message_id:
                target = m
                break
        if target is None:
            self._set_status_tpl("Message not found.")
            return False
        if not _is_transcript_message(target):
            self._set_status_tpl("Select a transcript message to summarize again.")
            return False
        if not (target.content or "").strip():
            self._set_status_tpl("Transcript is empty.")
            return False
        return True

    @Slot(str, str)
    def commitSummarizeAgain(self, message_id: str, llm_instructions: str) -> None:
        if not self.summarizeAgainValidated(message_id):
            return
        sid = self._session_id
        if not sid:
            return
        msgs = self._repo.list_messages(sid)
        idx: int | None = None
        target: Message | None = None
        for i, m in enumerate(msgs):
            if m.id == message_id:
                idx = i
                target = m
                break
        assert idx is not None and target is not None
        text = (target.content or "").strip()
        text = self._maybe_apply_stored_speaker_mapping(sid, text)
        llm_s = (llm_instructions or "").strip()
        prompt_ctx = run_prompt_context(llm_instructions=llm_s, whisper_context="")
        self._run_summarize_worker(sid, text, prompt_ctx)

    @Slot()
    def processRecorderOutput(self) -> None:
        path = self._recording.stopRecording()
        if path and Path(path).is_file():
            self.stageAudioFile(path)
        else:
            self._set_status_tpl("No recording file.")

    @Slot()
    def startPipelineFromRecorder(self) -> None:
        if self._pending_audio_path:
            self._set_status_tpl("Send or clear the staged audio file before recording.")
            return
        sid = self._session_id
        if not sid:
            self._set_status_tpl("No active session.")
            return
        session = ensure_repo_session_has_slug(self._repo, sid)
        dirs = resolve_session_meeting_dirs(self._repo, session)
        dirs.recordings.mkdir(parents=True, exist_ok=True)
        self._recording.startRecording(str(dirs.recordings))

    @Slot()
    def stopRecorderAndRunPipeline(self) -> None:
        self.processRecorderOutput()

    def _start_pipeline(
        self,
        audio_path: Path,
        *,
        add_user_row: bool = True,
        llm_instructions: str = "",
        whisper_context: str = "",
    ) -> None:
        if self._pipeline_start_globally_blocked():
            self._set_status_tpl(self._pipeline_start_block_user_tpl())
            return
        if not config.USE_MOCK_BACKEND and not self._transcription_ready():
            self._set_status_tpl("Speech model missing — open Settings and download Whisper.")
            return
        sid = self._session_id
        if not sid:
            return
        if self._repo.get_session(sid) is None:
            return
        self._status_clear_timer.stop()
        self._clear_stt_pipeline_log()
        self._pipeline_session_id = sid
        llm_stripped = (llm_instructions or "").strip()
        whisper_stripped = (whisper_context or "").strip()
        prompt_ctx = run_prompt_context(
            llm_instructions=llm_stripped,
            whisper_context=whisper_stripped,
        )
        self._pending_prompt_ctx = prompt_ctx
        prep = prepare_pipeline_audio_and_stem(
            self._repo,
            sid,
            audio_path,
            prompt_context=prompt_ctx,
        )
        working_audio = prep.working_audio
        artifact_stem = prep.artifact_stem
        out_dirs = prep.output_dirs
        self._pipeline_audio_path = working_audio
        self._set_busy(True)
        self._set_phase("transcribing")
        self._set_status_tpl("Transcribing…")
        name = working_audio.name
        if add_user_row:
            self._repo.add_message(
                sid,
                MessageRole.USER.value,
                f"Audio: {name}",
                str(working_audio),
                recording_llm_instructions=llm_stripped if llm_stripped else "",
                recording_whisper_context=whisper_stripped if whisper_stripped else "",
            )
            self._reload_messages()

        worker = TranscriptionWorker(
            sid,
            working_audio,
            artifact_stem,
            self._transcription,
            prompt_ctx,
            out_dirs,
            self,
        )
        trace_step(
            "ChatController transcription worker starting session=%s stem=%s audio=%s mock=%s",
            sid,
            artifact_stem,
            working_audio.name,
            config.USE_MOCK_BACKEND,
        )
        self._worker = worker
        worker.phase_changed.connect(self._on_phase)
        worker.transcription_event.connect(self._on_transcription_event)
        worker.finished_raw.connect(self._on_transcription_finished_raw)
        worker.failed.connect(self._on_transcription_failed)
        worker.interrupted.connect(self._on_transcription_interrupted)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_phase(self, phase: str) -> None:
        self._set_phase(phase)
        if phase == "transcribing":
            self._set_status_tpl("Transcribing…")
        elif phase == "summarizing":
            self._set_status_tpl("Generating summary…")
        else:
            self._set_status_empty()

    def _on_transcription_event(self, kind: str, message: str) -> None:
        self._append_stt_pipeline_event(kind, message)
        self._set_status_free(message)
        if kind not in (MessageSystemKind.WARNING.value, MessageSystemKind.ERROR.value):
            return
        sid = self._pipeline_session_id
        if sid and self._repo.get_session(sid) is not None:
            self._repo.add_message(
                sid, MessageRole.SYSTEM.value, message, None, system_kind=kind
            )
            self._reload_messages()

    def _maybe_apply_stored_speaker_mapping(self, session_id: str, text: str) -> str:
        if not extract_speaker_keys(text):
            return text
        rows = self._repo.list_session_speakers(session_id)
        if not rows:
            return text
        return apply_speaker_mapping(text, dict(rows))

    def _run_summarize_worker(
        self, session_id: str, transcript_text: str, ctx: PipelinePromptContext
    ) -> None:
        self._status_clear_timer.stop()
        self._summarize_session_id = session_id
        self._set_busy(True)
        self._set_phase("summarizing")
        self._set_status_tpl("Generating summary…")
        system = compose_llm_system_prompt(ctx)
        worker = SummarizeWorker(transcript_text, system, self._summarization, self)
        self._summarize_worker = worker
        worker.completed.connect(self._on_summarize_completed)
        worker.failed.connect(self._on_summarize_failed)
        worker.interrupted.connect(self._on_summarize_interrupted)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _clear_intercept_fields(self) -> None:
        self._stop_speaker_sample_playback()
        self._speaker_sample_stop_timer.stop()
        self._intercept_session_id = None
        self._intercept_raw_transcript = ""
        self._intercept_txt_path = ""
        self._intercept_transcript_message_id = ""
        self._intercept_map_message_id = ""
        self._intercept_speaker_keys = []
        self._intercept_speaker_time_ranges = {}
        self._intercept_prompt_ctx = None
        self._emit_pipeline_guards_changed()
        self.speakerSampleContextChanged.emit()

    @Slot(str, str, list)
    def _on_transcription_finished_raw(self, transcript: str, txt_path: str, keys: list) -> None:
        self._worker = None
        sid = self._pipeline_session_id
        if not sid or self._repo.get_session(sid) is None:
            self._clear_intercept_fields()
            self._finish_pipeline()
            return
        keys_list = [str(x) for x in (keys or [])]
        tr = self._repo.add_message(
            sid,
            MessageRole.ASSISTANT.value,
            transcript,
            txt_path,
            assistant_kind=AssistantContentKind.TRANSCRIPT.value,
        )
        if not keys_list:
            self._repo.replace_session_speakers(sid, {})
            ctx = self._pending_prompt_ctx
            self._pending_prompt_ctx = None
            if ctx is None:
                ctx = run_prompt_context(llm_instructions="", whisper_context="")
            self._reload_messages()
            self._run_summarize_worker(sid, transcript, ctx)
            self._pipeline_session_id = None
            self._pipeline_audio_path = None
            return
        payload = json.dumps({"keys": keys_list})
        mp = self._repo.add_message(
            sid,
            MessageRole.ASSISTANT.value,
            payload,
            None,
            assistant_kind=AssistantContentKind.SPEAKER_MAP.value,
        )
        self._intercept_session_id = sid
        self._intercept_raw_transcript = transcript
        self._intercept_txt_path = txt_path
        self._intercept_transcript_message_id = tr.id
        self._intercept_map_message_id = mp.id
        self._intercept_speaker_keys = keys_list
        self._intercept_speaker_time_ranges = first_time_range_sec_by_speaker(transcript)
        self._intercept_prompt_ctx = self._pending_prompt_ctx
        self._pending_prompt_ctx = None
        self._reload_messages()
        self._set_busy(False)
        self._set_phase("awaiting_speaker_map")
        self._set_status_tpl("Name each speaker, then confirm to generate the summary.")
        self.speakerSampleContextChanged.emit()

    @Slot(str)
    def _on_transcription_failed(self, message: str) -> None:
        _log.error("Transcription error: %s", message)
        self._status_clear_timer.stop()
        sid = self._pipeline_session_id
        self._clear_intercept_fields()
        if sid and self._repo.get_session(sid) is not None:
            err_path = str(self._pipeline_audio_path) if self._pipeline_audio_path else None
            self._repo.add_message(
                sid,
                MessageRole.SYSTEM.value,
                message,
                err_path,
                system_kind=MessageSystemKind.ERROR.value,
            )
            self._reload_messages()
        self._set_status_free(self.tr("Error") + ": " + message)
        self._set_phase("idle")
        self._finish_pipeline()

    def _finish_pipeline(self) -> None:
        self._set_busy(False)
        self._clear_stt_pipeline_log()
        self._worker = None
        self._pipeline_audio_path = None
        self._pipeline_session_id = None
        self._clear_intercept_fields()

    @Slot(str, str)
    def confirmSpeakerNames(self, map_message_id: str, names_json: str) -> None:
        if self._phase != "awaiting_speaker_map":
            return
        if map_message_id != self._intercept_map_message_id:
            return
        sid = self._intercept_session_id
        if not sid or self._repo.get_session(sid) is None:
            self._clear_intercept_fields()
            self._finish_pipeline()
            return
        try:
            raw_names = json.loads(names_json or "{}")
        except json.JSONDecodeError:
            self._set_status_tpl("Invalid speaker data.")
            return
        if not isinstance(raw_names, dict):
            self._set_status_tpl("Invalid speaker data.")
            return
        mapping: dict[str, str] = {}
        for k in self._intercept_speaker_keys:
            v = raw_names.get(k)
            if isinstance(v, str):
                mapping[k] = v.strip() or k
            elif v is not None:
                mapping[k] = str(v).strip() or k
            else:
                mapping[k] = k
        self._repo.replace_session_speakers(sid, mapping)
        raw = self._intercept_raw_transcript
        mapped = apply_speaker_mapping(raw, mapping)
        tp = (self._intercept_txt_path or "").strip()
        if tp:
            try:
                out = mapped if mapped.endswith("\n") else mapped + "\n"
                Path(tp).write_text(out, encoding="utf-8")
            except OSError as e:
                _log.warning("Could not rewrite transcript file: %s", e)
        tid = self._intercept_transcript_message_id
        ctx = self._intercept_prompt_ctx
        self._clear_intercept_fields()
        self._repo.update_assistant_message_content(sid, tid, mapped)
        self._repo.delete_message(sid, map_message_id)
        self._reload_messages()
        self._pipeline_session_id = None
        self._pipeline_audio_path = None
        if ctx is None:
            ctx = run_prompt_context(llm_instructions="", whisper_context="")
        self._run_summarize_worker(sid, mapped, ctx)

    @Slot(str)
    @Slot(str)
    def cancelSpeakerMapping(self, map_message_id: str) -> None:
        if self._phase != "awaiting_speaker_map":
            return
        if map_message_id != self._intercept_map_message_id:
            return
        sid = self._intercept_session_id
        if sid and self._repo.get_session(sid) is not None:
            self._repo.delete_message(sid, map_message_id)
            self._repo.add_message(
                sid,
                MessageRole.SYSTEM.value,
                self.tr("Speaker naming was cancelled."),
                None,
                system_kind=MessageSystemKind.INFO.value,
            )
            self._reload_messages()
        self._clear_intercept_fields()
        self._set_phase("idle")
        self._finish_pipeline()

    def _on_summarize_completed(self, summary: str) -> None:
        sid = self._summarize_session_id
        self._summarize_session_id = None
        self._summarize_worker = None
        if not sid:
            self._finish_pipeline()
            return
        if self._repo.get_session(sid) is None:
            self._finish_pipeline()
            return
        self._status_clear_timer.stop()
        session = ensure_repo_session_has_slug(self._repo, sid)
        dirs = resolve_session_meeting_dirs(self._repo, session)
        dirs.summaries.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        base_stem = build_meeting_artifact_stem(session.title, sid, now=now)
        stem = resolve_unique_summary_stem_in_dir(base_stem, dirs.summaries)
        summary_path = write_summary_txt(dirs.summaries, stem, summary)
        self._repo.add_message(
            sid,
            MessageRole.ASSISTANT.value,
            summary,
            str(summary_path),
            assistant_kind=AssistantContentKind.SUMMARY.value,
        )
        self._reload_messages()
        self._set_phase("idle")
        self._set_status_tpl("Done.")
        self._status_clear_timer.start()
        self._finish_pipeline()

    def _on_summarize_failed(self, message: str) -> None:
        _log.error("Summarize-only error: %s", message)
        self._status_clear_timer.stop()
        sid = self._summarize_session_id
        self._summarize_session_id = None
        self._summarize_worker = None
        if sid and self._repo.get_session(sid) is not None:
            self._repo.add_message(
                sid,
                MessageRole.SYSTEM.value,
                message,
                None,
                system_kind=MessageSystemKind.ERROR.value,
            )
            self._reload_messages()
        self._set_status_free(self.tr("Error") + ": " + message)
        self._set_phase("idle")
        self._set_busy(False)
        self._finish_pipeline()

    @Slot(str)
    def openFile(self, path: str) -> None:
        if not path:
            return
        p = Path(path)
        if not p.is_file():
            self._set_status_tpl("File no longer exists.")
            return
        url = QUrl.fromLocalFile(str(p.resolve()))
        QDesktopServices.openUrl(url)

    @Slot(str)
    def openExternalLink(self, url: str) -> None:
        raw = (url or "").strip()
        if not raw:
            return
        q = QUrl(raw)
        if q.scheme().lower() not in ("http", "https"):
            self._set_status_tpl("Only http and https links can be opened.")
            self._status_clear_timer.start()
            return
        if not q.isValid() or not q.host():
            self._set_status_tpl("Invalid link.")
            self._status_clear_timer.start()
            return
        QDesktopServices.openUrl(q)

    @Slot()
    def copyAppDataPath(self) -> None:
        app_inst = QGuiApplication.instance()
        if app_inst is not None:
            app_inst.clipboard().setText(str(config.DATA_DIR))
        self._set_status_tpl("Data path copied to clipboard.")
        self._status_clear_timer.start()

    @Slot()
    def copyMeetingOutputRoot(self) -> None:
        app_inst = QGuiApplication.instance()
        if app_inst is not None:
            app_inst.clipboard().setText(str(resolve_meeting_output_dirs(self._repo).root))
        self._set_status_tpl("Meeting files folder copied to clipboard.")
        self._status_clear_timer.start()

    @Slot(str)
    def showTransientStatus(self, msg: str) -> None:
        self._status_clear_timer.stop()
        self._set_status_free(msg)

    @Slot(str)
    def copyMessageFormatted(self, message_id: str) -> None:
        mid = (message_id or "").strip()
        if not mid or not self._session_id:
            self._set_status_tpl("Message not found.")
            return
        msg: Message | None = None
        for m in self._repo.list_messages(self._session_id):
            if m.id == mid:
                msg = m
                break
        if msg is None:
            self._set_status_tpl("Message not found.")
            return
        label = _message_copy_type_label(self.tr, msg)
        lines = [f"[{label}]"]
        if msg.created_at:
            lines.append(f"Time: {msg.created_at}")
        fp = (msg.file_path or "").strip()
        if fp:
            lines.append(f"File: {fp}")
        lines.append("")
        lines.append(msg.content or "")
        text = "\n".join(lines).strip() + "\n"
        app_inst = QGuiApplication.instance()
        if app_inst is not None:
            app_inst.clipboard().setText(text)
        self._set_status_tpl("Message copied to clipboard.")
        self._status_clear_timer.start()
