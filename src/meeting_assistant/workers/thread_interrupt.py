"""Small helpers for QThread workers."""

from __future__ import annotations

import time

from PySide6.QtCore import QThread


def interruptible_sleep_sec(thread: QThread, seconds: float) -> bool:
    """Sleep up to ``seconds`` in small steps; return True if ``thread`` is interrupted."""
    if seconds <= 0:
        return thread.isInterruptionRequested()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if thread.isInterruptionRequested():
            return True
        time.sleep(min(0.05, deadline - time.monotonic()))
    return thread.isInterruptionRequested()
