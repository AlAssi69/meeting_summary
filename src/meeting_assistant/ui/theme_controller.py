from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot


class ThemeController(QObject):
    """Dark/light palette: single source of truth for QML color bindings."""

    darkModeChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._dark = True

    @Property(bool, notify=darkModeChanged)
    def darkMode(self) -> bool:
        return self._dark

    @Slot()
    def toggleDarkMode(self) -> None:
        self._dark = not self._dark
        self.darkModeChanged.emit()

    @Property(str, notify=darkModeChanged)
    def windowBackground(self) -> str:
        return "#1a1b1e" if self._dark else "#f4f4f5"

    @Property(str, notify=darkModeChanged)
    def textPrimary(self) -> str:
        return "#e8e8ea" if self._dark else "#18181b"

    @Property(str, notify=darkModeChanged)
    def textMuted(self) -> str:
        return "#9a9aa3" if self._dark else "#52525b"

    @Property(str, notify=darkModeChanged)
    def surface(self) -> str:
        return "#25262b" if self._dark else "#ffffff"

    @Property(str, notify=darkModeChanged)
    def borderColor(self) -> str:
        return "#35363d" if self._dark else "#d4d4d8"

    @Property(str, notify=darkModeChanged)
    def chromeHover(self) -> str:
        return "#32353e" if self._dark else "#e4e4e8"

    @Property(str, notify=darkModeChanged)
    def chromePressed(self) -> str:
        return "#3d4150" if self._dark else "#d4d4d8"

    @Property(str, constant=True)
    def accent(self) -> str:
        return "#3b82f6"

    @Property(str, constant=True)
    def onAccentText(self) -> str:
        return "#ffffff"

    @Property(str, constant=True)
    def recordHot(self) -> str:
        return "#ea580c"

    @Property(str, notify=darkModeChanged)
    def userBubble(self) -> str:
        return "#2d3748" if self._dark else "#dbeafe"

    @Property(str, notify=darkModeChanged)
    def assistantBubble(self) -> str:
        return "#2a2d36" if self._dark else "#f4f4f5"

    @Property(str, notify=darkModeChanged)
    def transcriptCardBackground(self) -> str:
        """Whisper / STT assistant card (distinct from system info banners)."""
        return "#1a2426" if self._dark else "#f0fdfa"

    @Property(str, notify=darkModeChanged)
    def transcriptCardBorder(self) -> str:
        return "#2f5f52" if self._dark else "#5eead4"

    @Property(str, notify=darkModeChanged)
    def transcriptCardTitle(self) -> str:
        return "#5eead4" if self._dark else "#0f766e"

    @Property(str, notify=darkModeChanged)
    def summaryCardBackground(self) -> str:
        """LLM summary assistant card."""
        return "#221c2c" if self._dark else "#faf5ff"

    @Property(str, notify=darkModeChanged)
    def summaryCardBorder(self) -> str:
        return "#5b4d78" if self._dark else "#c4b5fd"

    @Property(str, notify=darkModeChanged)
    def summaryCardTitle(self) -> str:
        return "#c4b5fd" if self._dark else "#6d28d9"

    @Property(str, notify=darkModeChanged)
    def inputSurface(self) -> str:
        return "#1e1f24" if self._dark else "#fafafa"

    @Property(str, notify=darkModeChanged)
    def sessionListHover(self) -> str:
        return "#2e3038" if self._dark else "#eef0f4"

    @Property(str, notify=darkModeChanged)
    def linkHoverBackground(self) -> str:
        return "#3f3f46" if self._dark else "#eff6ff"

    @Property(str, notify=darkModeChanged)
    def headerChromeFill(self) -> str:
        """Header/settings outline button idle fill in light mode."""
        return "transparent" if self._dark else "#f4f4f5"

    @Property(str, notify=darkModeChanged)
    def errorBannerBackground(self) -> str:
        return "#2d1f1f" if self._dark else "#fef2f2"

    @Property(str, notify=darkModeChanged)
    def errorBannerBorder(self) -> str:
        return "#991b1b" if self._dark else "#fecaca"

    @Property(str, constant=True)
    def errorText(self) -> str:
        return "#ef4444"

    @Property(str, notify=darkModeChanged)
    def warningBannerBackground(self) -> str:
        return "#2d2618" if self._dark else "#fffbeb"

    @Property(str, notify=darkModeChanged)
    def warningBannerBorder(self) -> str:
        return "#b45309" if self._dark else "#fde68a"

    @Property(str, constant=True)
    def warningText(self) -> str:
        return "#f59e0b"

    @Property(str, notify=darkModeChanged)
    def infoBannerBackground(self) -> str:
        return "#1a2332" if self._dark else "#eff6ff"

    @Property(str, notify=darkModeChanged)
    def infoBannerBorder(self) -> str:
        return "#2563eb" if self._dark else "#bfdbfe"

    @Property(str, constant=True)
    def infoText(self) -> str:
        return "#60a5fa"
