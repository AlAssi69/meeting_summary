from __future__ import annotations

from PySide6.QtQml import QQmlApplicationEngine

from meeting_assistant import config
from meeting_assistant.adapters.memory_session_repository import InMemorySessionRepository
from meeting_assistant.adapters.mock_summarization import MockSummarizationAdapter
from meeting_assistant.adapters.mock_transcription import MockTranscriptionAdapter
from meeting_assistant.adapters.ollama_adapter import OllamaSummarizationAdapter
from meeting_assistant.adapters.sqlite_session_repository import SqliteSessionRepository
from meeting_assistant.adapters.whisperx_adapter import WhisperXTranscriptionAdapter
from meeting_assistant.ports.session_repository import SessionRepository
from meeting_assistant.ports.summarization import SummarizationPort
from meeting_assistant.ports.transcription import TranscriptionPort
from meeting_assistant.services.hf_token import resolve_hf_access_token
from meeting_assistant.services.transcription_audio_prep import build_transcription_audio_preparer
from meeting_assistant.services.whisperx_engine import WhisperXEngine
from meeting_assistant.ui.app_facade import AppFacade
from meeting_assistant.ui.locale_controller import LocaleController
from meeting_assistant.ui.model_status_controller import ModelStatusController


def build_repository() -> SessionRepository:
    if config.USE_MOCK_BACKEND:
        return InMemorySessionRepository()
    return SqliteSessionRepository(config.DB_PATH)


def build_summarization() -> SummarizationPort:
    if config.USE_MOCK_BACKEND:
        return MockSummarizationAdapter()
    return OllamaSummarizationAdapter()


def build_app_facade(engine: QQmlApplicationEngine) -> AppFacade:
    """Wire concrete adapters based on config (mock vs SQLite + WhisperX + Ollama)."""
    repo = build_repository()

    def _token_resolver() -> str:
        return resolve_hf_access_token(repo)

    speech_engine = WhisperXEngine(
        token_resolver=_token_resolver,
        audio_preparer=build_transcription_audio_preparer(),
    )
    if config.USE_MOCK_BACKEND:
        transcription: TranscriptionPort = MockTranscriptionAdapter()
    else:
        transcription = WhisperXTranscriptionAdapter(speech_engine)
    summarization = build_summarization()
    model_status = ModelStatusController(speech_engine)
    locale = LocaleController(repo, engine)
    return AppFacade(repo, transcription, summarization, model_status, locale)