from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from meeting_assistant import config

_log = logging.getLogger(__name__)


class DebugNotifier(QObject):
    """Emits user-visible debug messages when DEBUG_UI is enabled."""

    notify = Signal(str)

    def emit_debug(self, message: str) -> None:
        if not config.DEBUG_UI:
            return
        text = message if message.startswith("[DEBUG]") else f"[DEBUG] {message}"
        _log.debug("%s", text)
        self.notify.emit(text)


_notifier: DebugNotifier | None = None


def debug_notifier() -> DebugNotifier:
    global _notifier
    if _notifier is None:
        _notifier = DebugNotifier()
    return _notifier


def debug_notify(message: str) -> None:
    debug_notifier().emit_debug(message)
