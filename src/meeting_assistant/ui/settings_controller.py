from __future__ import annotations

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from meeting_assistant.ports.session_repository import SessionRepository
from meeting_assistant.services.output_paths import resolve_meeting_output_dirs
from meeting_assistant.services.session_artifact_folder import prune_empty_session_artifact_folders


class SettingsController(QObject):
    """Meeting file output folder and HF token (persisted via repository)."""

    meetingFilesFolderChanged = Signal()
    meetingOutputRootCustomChanged = Signal()
    hfAccessTokenConfiguredChanged = Signal()

    def __init__(self, repo: SessionRepository, parent=None) -> None:
        super().__init__(parent)
        self._repo = repo

    @Property(str, notify=meetingFilesFolderChanged)
    def meetingFilesFolder(self) -> str:
        return str(resolve_meeting_output_dirs(self._repo).root)

    @Property(str, notify=meetingOutputRootCustomChanged)
    def meetingOutputRootCustom(self) -> str:
        return self._repo.get_meeting_output_root()

    @Slot(str)
    def setMeetingOutputRoot(self, value: str) -> None:
        raw = (value or "").strip()
        if raw.startswith("file:"):
            raw = QUrl(raw).toLocalFile()
        self._repo.set_meeting_output_root(raw)
        self.meetingFilesFolderChanged.emit()
        self.meetingOutputRootCustomChanged.emit()

    @Slot(QUrl)
    def setMeetingOutputRootFromUrl(self, url: QUrl) -> None:
        path = url.toLocalFile()
        self._repo.set_meeting_output_root(path.strip())
        self.meetingFilesFolderChanged.emit()
        self.meetingOutputRootCustomChanged.emit()

    @Slot()
    def resetMeetingOutputRoot(self) -> None:
        self._repo.set_meeting_output_root("")
        self.meetingFilesFolderChanged.emit()
        self.meetingOutputRootCustomChanged.emit()

    @Slot()
    def copyMeetingFilesFolderPath(self) -> None:
        app_inst = QGuiApplication.instance()
        if app_inst is not None:
            app_inst.clipboard().setText(self.meetingFilesFolder)

    @Slot(result=int)
    def pruneEmptySessionFolders(self) -> int:
        return prune_empty_session_artifact_folders(self._repo)

    @Property(bool, notify=hfAccessTokenConfiguredChanged)
    def hfAccessTokenConfigured(self) -> bool:
        return bool((self._repo.get_hf_access_token() or "").strip())

    @Slot(str)
    def setHfAccessToken(self, value: str) -> None:
        self._repo.set_hf_access_token(value or "")
        self.hfAccessTokenConfiguredChanged.emit()

    @Slot(str, result=bool)
    def hfTokenPreviewLooksValid(self, preview: str) -> bool:
        s = (preview or "").strip()
        return len(s) >= 8 and s.startswith("hf_")
