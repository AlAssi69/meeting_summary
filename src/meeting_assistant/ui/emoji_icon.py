"""Build QIcon from a single emoji for window/taskbar icons (best-effort per platform font)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap


def icon_from_emoji(emoji: str, pixel_size: int = 64) -> QIcon:
    px = max(16, min(pixel_size, 256))
    pix = QPixmap(QSize(px, px))
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    font = QFont()
    font.setPixelSize(int(px * 0.62))
    font.setFamilies(
        [
            "Segoe UI Emoji",
            "Apple Color Emoji",
            "Noto Color Emoji",
            "Segoe UI Symbol",
            "sans-serif",
        ]
    )
    painter.setFont(font)
    painter.drawText(pix.rect(), int(Qt.AlignmentFlag.AlignCenter), emoji)
    painter.end()
    return QIcon(pix)
