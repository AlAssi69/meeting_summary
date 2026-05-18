from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from meeting_assistant import config
from meeting_assistant.ports.transcription import TranscriptionPort
from meeting_assistant.services.output_paths import MeetingOutputDirs
from meeting_assistant.services.prompt_composition import (
    PipelinePromptContext,
    compose_whisper_initial_prompt,
)
from meeting_assistant.services.speaker_mapping import extract_speaker_keys
from meeting_assistant.services.transcript_file import write_transcript_txt
from meeting_assistant.services.transcript_jargon_normalizer import maybe_normalize_transcript
from meeting_assistant.services.transcription_cancelled import TranscriptionCancelled
from meeting_assistant.trace import trace_main
from meeting_assistant.workers.thread_interrupt import interruptible_sleep_sec

_log = logging.getLogger(__name__)


class TranscriptionWorker(QThread):
    """Transcribe + write transcript only (no summarization)."""

    phase_changed = Signal(str)
    transcription_event = Signal(str, str)
    finished_raw = Signal(str, str, list)
    failed = Signal(str)
    interrupted = Signal(str, str)

    def __init__(
        self,
        session_id: str,
        audio_path: Path,
        artifact_stem: str,
        transcription: TranscriptionPort,
        prompt_context: PipelinePromptContext,
        output_dirs: MeetingOutputDirs,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._session_id = session_id
        self._audio_path = audio_path
        self._artifact_stem = artifact_stem
        self._transcription = transcription
        self._prompt_context = prompt_context
        self._output_dirs = output_dirs

    def _emit_notices(self) -> None:
        notices_cb = getattr(self._transcription, "consume_transcription_notices", None)
        if callable(notices_cb):
            for kind, msg in notices_cb():
                self.transcription_event.emit(kind, msg)

    def run(self) -> None:
        text = ""
        txt_path: Path | None = None
        try:
            trace_main(
                "TranscriptionWorker started session=%s stem=%s audio=%s",
                self._session_id,
                self._artifact_stem,
                self._audio_path.name,
            )
            if self.isInterruptionRequested():
                self.interrupted.emit("", "")
                return
            if config.USE_MOCK_BACKEND and interruptible_sleep_sec(
                self, config.MOCK_PIPELINE_DELAY_SEC
            ):
                self.interrupted.emit("", "")
                return
            self.phase_changed.emit("transcribing")
            initial = compose_whisper_initial_prompt(self._prompt_context)
            try:
                text = self._transcription.transcribe(
                    self._audio_path,
                    initial_prompt=initial,
                    cancel_check=self.isInterruptionRequested,
                )
            except TranscriptionCancelled:
                self.interrupted.emit("", "")
                return
            trace_main(
                "TranscriptionWorker transcribe returned session=%s chars=%d",
                self._session_id,
                len(text),
            )
            self._emit_notices()
            text = maybe_normalize_transcript(text, self._prompt_context)
            if self.isInterruptionRequested():
                self.interrupted.emit("", "")
                return
            txt_path = write_transcript_txt(
                self._output_dirs.transcripts, self._artifact_stem, text
            )
            trace_main(
                "TranscriptionWorker wrote transcript session=%s path=%s",
                self._session_id,
                txt_path,
            )
            self._transcription.release_transcription_accelerator_memory()
            if self.isInterruptionRequested():
                self.interrupted.emit(text, str(txt_path))
                return
            if config.USE_MOCK_BACKEND and interruptible_sleep_sec(
                self, config.MOCK_PIPELINE_DELAY_SEC
            ):
                self.interrupted.emit(text, str(txt_path))
                return
            if self.isInterruptionRequested():
                self.interrupted.emit(text, str(txt_path))
                return
            keys = extract_speaker_keys(text)
            self.finished_raw.emit(text, str(txt_path), keys)
        except Exception as e:
            _log.exception("Transcription failed")
            trace_main("TranscriptionWorker failed session=%s error=%s", self._session_id, e)
            self._emit_notices()
            if text and txt_path is not None:
                self.interrupted.emit(text, str(txt_path))
            else:
                self.failed.emit(str(e))
