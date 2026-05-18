"""Runtime Arabic translator using an in-memory catalog (no external .qm tools required)."""

from __future__ import annotations

from PySide6.QtCore import QTranslator

from meeting_assistant.i18n.ar_catalog import AR_UI


class ArabicCatalogTranslator(QTranslator):
    """Looks up (context, source) in AR_UI; None defers to the next translator or source text."""

    def translate(
        self,
        context: bytes | str,
        source_text: str,
        disambiguation: str | None = None,
        n: int = -1,
    ) -> str | None:
        _ = disambiguation
        _ = n
        if not source_text:
            return ""
        ctx = (
            context.decode("utf-8")
            if isinstance(context, (bytes, bytearray))
            else (context or "")
        )
        hit = AR_UI.get((ctx, source_text))
        if hit is not None:
            return hit
        return None
