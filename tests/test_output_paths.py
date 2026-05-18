from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from meeting_assistant.adapters.memory_session_repository import InMemorySessionRepository
from meeting_assistant.core.models import Session
from meeting_assistant.services.output_paths import resolve_meeting_output_dirs
from meeting_assistant.services.session_artifact_folder import (
    prune_empty_session_artifact_folders,
    resolve_session_meeting_dirs,
)
from meeting_assistant.services.transcript_file import (
    build_meeting_artifact_stem,
    rename_temp_recording_if_needed,
    resolve_unique_pipeline_stem,
    resolve_unique_pipeline_stem_in_dir,
    resolve_unique_summary_stem,
    resolve_unique_summary_stem_in_dir,
    sanitize_title_for_filename,
    write_summary_txt,
    write_transcript_txt,
)


def test_resolve_custom_from_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MEETING_ASSISTANT_OUTPUT_ROOT", raising=False)
    repo = InMemorySessionRepository()
    custom = tmp_path / "my_out"
    repo.set_meeting_output_root(str(custom))
    dirs = resolve_meeting_output_dirs(repo)
    assert dirs.root == custom.resolve()
    assert dirs.recordings == custom.resolve() / "recordings"
    assert dirs.transcripts == custom.resolve() / "transcripts"
    assert dirs.summaries == custom.resolve() / "summaries"


def test_write_transcript_and_summary_pairing(tmp_path: Path) -> None:
    stem = "Weekly_sync_20200101_000000Z"
    tr_dir = tmp_path / "tr"
    sm_dir = tmp_path / "sm"
    p1 = write_transcript_txt(tr_dir, stem, "hello")
    p2 = write_summary_txt(sm_dir, stem, "sum")
    assert p1.read_text(encoding="utf-8") == "hello"
    assert p2.read_text(encoding="utf-8") == "sum"
    assert p2.name == f"{stem}.summary.txt"


def test_sanitize_title_for_filename_strips_forbidden_chars() -> None:
    assert sanitize_title_for_filename('a<b>c:"/\\|?*d') == "a_b_c_d"


def test_sanitize_title_for_filename_truncates() -> None:
    long_title = "x" * 100
    out = sanitize_title_for_filename(long_title, max_len=40)
    assert len(out) == 40


def test_sanitize_title_preserves_unicode() -> None:
    assert "اجتماع" in sanitize_title_for_filename("اجتماع الفريق")


def test_build_meeting_artifact_stem_uses_utc_stamp() -> None:
    fixed = datetime(2026, 5, 5, 10, 30, 45, tzinfo=timezone.utc)
    s = build_meeting_artifact_stem("My Meeting", "sid-1", now=fixed)
    assert s.startswith("My_Meeting_")
    assert "20260505_103045Z" in s


def test_resolve_unique_pipeline_stem_appends_suffix_when_taken(tmp_path: Path) -> None:
    rec = tmp_path / "r"
    tr = tmp_path / "t"
    sm = tmp_path / "s"
    for d in (rec, tr, sm):
        d.mkdir()
    base = "Meet_20260505_120000Z"
    (tr / f"{base}.txt").write_text("x", encoding="utf-8")
    assert resolve_unique_pipeline_stem(base, rec, tr, sm) == f"{base}_2"


def test_resolve_unique_summary_stem_when_summary_exists(tmp_path: Path) -> None:
    sm = tmp_path / "s"
    sm.mkdir()
    base = "Meet_20260505_120000Z"
    (sm / f"{base}.summary.txt").write_text("x", encoding="utf-8")
    assert resolve_unique_summary_stem(base, sm) == f"{base}_2"


def test_rename_temp_recording_if_needed(tmp_path: Path) -> None:
    rec = tmp_path / "recordings"
    rec.mkdir()
    temp = rec / "mtg_rec_abcd.m4a"
    temp.write_bytes(b"\x00")
    stem = "Welcome_20260505_120000Z"
    out = rename_temp_recording_if_needed(temp, rec, stem)
    assert out == rec / f"{stem}.m4a"
    assert out.is_file()
    assert not temp.exists()


def test_resolve_unique_pipeline_stem_in_dir(tmp_path: Path) -> None:
    d = tmp_path / "session1"
    d.mkdir()
    base = "Meet_20260505_120000Z"
    (d / f"{base}.txt").write_text("x", encoding="utf-8")
    assert resolve_unique_pipeline_stem_in_dir(base, d) == f"{base}_2"


def test_resolve_unique_summary_stem_in_dir(tmp_path: Path) -> None:
    d = tmp_path / "s"
    d.mkdir()
    base = "Meet_20260505_120000Z"
    (d / f"{base}.summary.txt").write_text("x", encoding="utf-8")
    assert resolve_unique_summary_stem_in_dir(base, d) == f"{base}_2"


def test_resolve_session_meeting_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MEETING_ASSISTANT_OUTPUT_ROOT", raising=False)
    repo = InMemorySessionRepository()
    repo.set_meeting_output_root(str(tmp_path))
    session = Session(id="id1", title="T", created_at="t", artifacts_slug="MySession")
    dirs = resolve_session_meeting_dirs(repo, session)
    assert dirs.recordings == dirs.transcripts == dirs.summaries
    assert dirs.recordings == tmp_path.resolve() / "sessions" / "MySession"


def test_create_session_does_not_create_sessions_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("MEETING_ASSISTANT_OUTPUT_ROOT", raising=False)
    repo = InMemorySessionRepository()
    repo.set_meeting_output_root(str(tmp_path))
    repo.create_session("Hi")
    assert not (tmp_path / "sessions").exists()


def test_prune_empty_session_artifact_folders(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("MEETING_ASSISTANT_OUTPUT_ROOT", raising=False)
    repo = InMemorySessionRepository()
    repo.set_meeting_output_root(str(tmp_path))
    sr = tmp_path / "sessions"
    sr.mkdir()
    (sr / "empty_a").mkdir()
    (sr / "empty_b").mkdir()
    (sr / "has_file").mkdir()
    (sr / "has_file" / "x.txt").write_text("x", encoding="utf-8")
    assert prune_empty_session_artifact_folders(repo) == 2
    assert not (sr / "empty_a").exists()
    assert not (sr / "empty_b").exists()
    assert (sr / "has_file" / "x.txt").is_file()


def test_allocate_unique_session_slug(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MEETING_ASSISTANT_OUTPUT_ROOT", raising=False)
    repo = InMemorySessionRepository()
    repo.set_meeting_output_root(str(tmp_path))
    s1 = repo.create_session("Same")
    assert s1.artifacts_slug == sanitize_title_for_filename("Same")
    s2 = repo.create_session("Same")
    assert s1.artifacts_slug != s2.artifacts_slug


def test_rename_temp_skipped_for_paths_outside_recordings(tmp_path: Path) -> None:
    rec = tmp_path / "recordings"
    rec.mkdir()
    other = tmp_path / "elsewhere"
    other.mkdir()
    temp = other / "mtg_rec_abcd.m4a"
    temp.write_bytes(b"\x00")
    out = rename_temp_recording_if_needed(temp, rec, "X_20260505_120000Z")
    assert out == temp
