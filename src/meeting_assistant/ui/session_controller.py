from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from meeting_assistant.ports.session_repository import SessionRepository
from meeting_assistant.services.session_artifact_folder import (
    allocate_unique_session_slug,
    try_rename_session_artifacts_folder,
)
from meeting_assistant.services.session_artifacts_cleanup import delete_session_disk_artifacts


class SessionController(QObject):
    """Sidebar: list sessions, create, select current."""

    sessionsChanged = Signal()
    currentSessionIdChanged = Signal()
    renameFailed = Signal(str)
    deleteFailed = Signal(str)

    def __init__(self, repo: SessionRepository, parent=None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._current_id: str | None = None
        if not self._repo.list_sessions():
            s = self._repo.create_session(self.tr("Welcome"))
            self._current_id = s.id
        else:
            self._current_id = self._repo.list_sessions()[0].id
        self.sessionsChanged.emit()

    @Property(str, notify=currentSessionIdChanged)
    def currentSessionId(self) -> str:
        return self._current_id or ""

    @Property(list, notify=sessionsChanged)
    def sessions(self) -> list:
        return [
            {"id": s.id, "title": s.title, "created": s.created_at}
            for s in self._repo.list_sessions()
        ]

    @Slot()
    def newSession(self) -> None:
        s = self._repo.create_session(self.tr("New meeting"))
        self._current_id = s.id
        self.sessionsChanged.emit()
        self.currentSessionIdChanged.emit()

    @Slot(str)
    def selectSession(self, session_id: str) -> None:
        if not session_id:
            return
        if self._repo.get_session(session_id) is None:
            return
        self._current_id = session_id
        self.currentSessionIdChanged.emit()

    @Slot(str, str)
    def renameSession(self, session_id: str, title: str) -> None:
        if not session_id or self._repo.get_session(session_id) is None:
            return
        name = title.strip()
        if not name:
            name = self.tr("Untitled")
        sess = self._repo.get_session(session_id)
        assert sess is not None
        old_slug = sess.artifacts_slug
        new_slug = allocate_unique_session_slug(
            self._repo,
            name,
            exclude_session_id=session_id,
            exclude_dir_name=old_slug,
        )
        if new_slug != old_slug:
            ok, err = try_rename_session_artifacts_folder(
                self._repo,
                old_slug=old_slug,
                new_slug=new_slug,
            )
            if not ok:
                self.renameFailed.emit(
                    self.tr("Could not rename meeting folder: {0}").format(err)
                )
                return
            self._repo.set_session_artifacts_slug(session_id, new_slug)
        self._repo.set_session_title(session_id, name)
        self.sessionsChanged.emit()

    @Slot(str)
    def deleteSession(self, session_id: str) -> None:
        if not session_id or self._repo.get_session(session_id) is None:
            return
        try:
            delete_session_disk_artifacts(self._repo, session_id)
        except OSError as e:
            self.deleteFailed.emit(
                self.tr("Some meeting files could not be deleted: {0}").format(e)
            )
        was_current = self._current_id == session_id
        self._repo.delete_session(session_id)
        if was_current:
            remaining = self._repo.list_sessions()
            if remaining:
                self._current_id = remaining[0].id
            else:
                s = self._repo.create_session(self.tr("Welcome"))
                self._current_id = s.id
            self.currentSessionIdChanged.emit()
        self.sessionsChanged.emit()

    def refresh(self) -> None:
        self.sessionsChanged.emit()
