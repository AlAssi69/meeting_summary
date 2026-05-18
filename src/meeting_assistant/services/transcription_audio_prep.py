"""Transcription audio preparer implementations and factory (DRY wiring)."""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from meeting_assistant import config
from meeting_assistant.ports.audio_preparation import TranscriptionAudioPreparer
from meeting_assistant.services.ffmpeg_audio_preprocess import (
    build_transcription_afilter_from_config,
    log_audio_prep_banner_start,
    log_audio_prep_keep_temp_notice,
    log_audio_prep_skipped,
    log_audio_prep_temp_removed,
    run_ffmpeg_transcription_prep,
)
from meeting_assistant.trace import trace_step

_log = logging.getLogger(__name__)


class NoOpTranscriptionAudioPreparer:
    """Passes through the original path (no FFmpeg)."""

    @contextmanager
    def prepare(self, source: Path) -> Iterator[Path]:
        log_audio_prep_skipped(source_name=source.name)
        yield source


class FfmpegWavTranscriptionAudioPreparer:
    """Writes a temporary 16 kHz mono WAV using FFmpeg; deletes it on exit unless keep-temp is set."""

    @contextmanager
    def prepare(self, source: Path) -> Iterator[Path]:
        if not source.is_file():
            _log.error("Audio prep: source file missing: %s", source)
            raise FileNotFoundError(str(source))
        afilter = build_transcription_afilter_from_config()
        fd, tmp_name = tempfile.mkstemp(suffix=".wav", prefix="meeting_assistant_prep_")
        os.close(fd)
        out_path = Path(tmp_name)
        log_audio_prep_banner_start(input_name=source.name, temp_name=out_path.name)
        trace_step(
            "Audio prep FFmpeg scheduled input=%s afilter=%s",
            source.name,
            afilter,
        )
        try:
            run_ffmpeg_transcription_prep(
                source,
                out_path,
                afilter=afilter,
                sample_rate=config.AUDIO_PREP_OUTPUT_SAMPLE_RATE,
                timeout_sec=config.AUDIO_PREP_FFMPEG_TIMEOUT_SEC,
            )
            trace_step("Audio prep temp ready path=%s", out_path.name)
            yield out_path
        finally:
            if config.AUDIO_PREP_KEEP_TEMP:
                log_audio_prep_keep_temp_notice(str(out_path))
            else:
                try:
                    out_path.unlink(missing_ok=True)
                    log_audio_prep_temp_removed(out_path.name)
                except OSError as e:
                    _log.warning("Audio prep could not remove temp %s: %s", out_path, e)


def build_transcription_audio_preparer() -> TranscriptionAudioPreparer:
    """Select preparer from application config."""
    if not config.AUDIO_PREP_ENABLED:
        return NoOpTranscriptionAudioPreparer()
    return FfmpegWavTranscriptionAudioPreparer()
