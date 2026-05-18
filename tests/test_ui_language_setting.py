from pathlib import Path

from meeting_assistant.adapters.sqlite_session_repository import SqliteSessionRepository
from meeting_assistant.core.constants import DEFAULT_UI_LANGUAGE


def test_ui_language_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    repo = SqliteSessionRepository(db)
    assert repo.get_ui_language() == DEFAULT_UI_LANGUAGE
    repo.set_ui_language("en")
    assert repo.get_ui_language() == "en"
    repo.set_ui_language("ar")
    assert repo.get_ui_language() == "ar"
    repo.set_ui_language("invalid")
    assert repo.get_ui_language() == DEFAULT_UI_LANGUAGE
