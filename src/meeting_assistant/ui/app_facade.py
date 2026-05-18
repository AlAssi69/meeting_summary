from __future__ import annotations

from PySide6.QtCore import Property, QObject

from meeting_assistant.debug_util import debug_notifier
from meeting_assistant.ports.session_repository import SessionRepository
from meeting_assistant.ports.summarization import SummarizationPort
from meeting_assistant.ports.transcription import TranscriptionPort
from meeting_assistant.ui.chat_controller import ChatController
from meeting_assistant.ui.locale_controller import LocaleController
from meeting_assistant.ui.model_status_controller import ModelStatusController
from meeting_assistant.ui.session_controller import SessionController
from meeting_assistant.ui.settings_controller import SettingsController
from meeting_assistant.ui.theme_controller import ThemeController


class AppFacade(QObject):
    """Composition root exposed to QML as a single context object."""

    def __init__(
        self,
        repo: SessionRepository,
        transcription: TranscriptionPort,
        summarization: SummarizationPort,
        model_status: ModelStatusController,
        locale_controller: LocaleController,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._model_status = model_status
        self._locale = locale_controller
        self._session = SessionController(repo)
        self._chat = ChatController(
            repo,
            transcription,
            summarization,
            transcription_ready=model_status.is_transcription_ready,
        )
        self._settings = SettingsController(repo)
        self._theme = ThemeController()
        self._session.currentSessionIdChanged.connect(self._sync_session)
        self._session.renameFailed.connect(self._chat.showTransientStatus)
        self._session.deleteFailed.connect(self._chat.showTransientStatus)
        self._locale.languageChanged.connect(self._chat.refreshUiLanguage)
        self._locale.languageChanged.connect(self._model_status.refreshUiLanguage)
        self._sync_session()

    def _sync_session(self) -> None:
        self._chat.setCurrentSessionId(self._session.currentSessionId)

    @Property(QObject, constant=True)
    def sessionController(self) -> SessionController:
        return self._session

    @Property(QObject, constant=True)
    def chatController(self) -> ChatController:
        return self._chat

    @Property(QObject, constant=True)
    def settingsController(self) -> SettingsController:
        return self._settings

    @Property(QObject, constant=True)
    def themeController(self) -> ThemeController:
        return self._theme

    @Property(QObject, constant=True)
    def localeController(self) -> LocaleController:
        return self._locale

    @Property(QObject, constant=True)
    def modelStatusController(self) -> ModelStatusController:
        return self._model_status

    @Property(QObject, constant=True)
    def debugNotifier(self) -> QObject:
        return debug_notifier()
