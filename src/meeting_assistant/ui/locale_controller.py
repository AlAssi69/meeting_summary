from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Qt, QTranslator, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from meeting_assistant.i18n.dict_translator import ArabicCatalogTranslator
from meeting_assistant.ports.session_repository import SessionRepository


def translations_directory() -> Path:
    return Path(__file__).resolve().parent.parent / "translations"


class LocaleController(QObject):
    """Installs UI translations, sets application layout direction, and retranslates QML."""

    languageChanged = Signal()

    def __init__(
        self,
        repo: SessionRepository,
        engine: QQmlApplicationEngine,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repo
        self._engine = engine
        self._qm_translator = QTranslator(self)
        self._ar_translator = ArabicCatalogTranslator(self)
        self._language = self._repo.get_ui_language()
        self._apply_translation_and_direction(self._language, emit=False)

    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return self._language

    def _apply_translation_and_direction(self, code: str, *, emit: bool) -> None:
        app = QGuiApplication.instance()
        if app is not None:
            app.removeTranslator(self._qm_translator)
            app.removeTranslator(self._ar_translator)
        if code == "ar":
            path = translations_directory()
            qm = path / "meeting_assistant_ar.qm"
            if app is not None:
                app.installTranslator(self._ar_translator)
                if qm.is_file():
                    self._qm_translator.load(str(qm))
                    app.installTranslator(self._qm_translator)
            if app is not None:
                app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        else:
            if app is not None:
                app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._language = code
        self._engine.retranslate()
        if emit:
            self.languageChanged.emit()

    @Slot(str)
    def setLanguage(self, code: str) -> None:
        raw = (code or "").strip().lower()
        if raw not in ("ar", "en"):
            return
        if raw == self._language:
            return
        self._repo.set_ui_language(raw)
        self._apply_translation_and_direction(raw, emit=True)
