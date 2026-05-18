from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

_WIN_FORBIDDEN = frozenset('<>:"/\\|?*')
_TITLE_MAX_LEN = 60


def sanitize_title_for_filename(title: str, *, max_len: int = _TITLE_MAX_LEN) -> str:
    """Turn a session title into a single filesystem-safe segment (Unicode allowed)."""
    parts: list[str] = []
    for ch in title.strip():
        if ord(ch) < 32 or ch in _WIN_FORBIDDEN:
            parts.append("_")
        else:
            parts.append(ch)
    merged = "".join(parts)
    merged = re.sub(r"[\s_]+", "_", merged.strip())
    merged = merged.strip("_")
    if len(merged) > max_len:
        merged = merged[:max_len].rstrip("_")
    return merged or "Meeting"


def build_meeting_artifact_stem(title: str, _session_id: str, *, now: datetime | None = None) -> str:
    """Human-readable stem: sanitized title + UTC timestamp."""
    when = now if now is not None else datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    else:
        when = when.astimezone(timezone.utc)
    readable = sanitize_title_for_filename(title.strip() or "Meeting")
    stamp = when.strftime("%Y%m%d_%H%M%SZ")
    return f"{readable}_{stamp}"


def _pipeline_stem_taken(stem: str, recordings: Path, transcripts: Path, summaries: Path) -> bool:
    if (recordings / f"{stem}.m4a").exists():
        return True
    if (transcripts / f"{stem}.txt").exists():
        return True
    if (summaries / f"{stem}.summary.txt").exists():
        return True
    return False


def _pipeline_stem_taken_in_dir(artifact_dir: Path, stem: str) -> bool:
    if (artifact_dir / f"{stem}.m4a").exists():
        return True
    if (artifact_dir / f"{stem}.txt").exists():
        return True
    if (artifact_dir / f"{stem}.summary.txt").exists():
        return True
    return False


def resolve_unique_pipeline_stem(
    base_stem: str,
    recordings: Path,
    transcripts: Path,
    summaries: Path,
) -> str:
    """Append _2, _3, … if transcript, summary, or recording with this stem already exists."""
    stem = base_stem
    n = 2
    while _pipeline_stem_taken(stem, recordings, transcripts, summaries):
        stem = f"{base_stem}_{n}"
        n += 1
    return stem


def resolve_unique_pipeline_stem_in_dir(base_stem: str, artifact_dir: Path) -> str:
    """Unique stem when audio, transcript, and summary share one directory."""
    stem = base_stem
    n = 2
    while _pipeline_stem_taken_in_dir(artifact_dir, stem):
        stem = f"{base_stem}_{n}"
        n += 1
    return stem


def resolve_unique_summary_stem(base_stem: str, summaries: Path) -> str:
    stem = base_stem
    n = 2
    while (summaries / f"{stem}.summary.txt").exists():
        stem = f"{base_stem}_{n}"
        n += 1
    return stem


def resolve_unique_summary_stem_in_dir(base_stem: str, artifact_dir: Path) -> str:
    stem = base_stem
    n = 2
    while (artifact_dir / f"{stem}.summary.txt").exists():
        stem = f"{base_stem}_{n}"
        n += 1
    return stem


def rename_temp_recording_if_needed(audio_path: Path, recordings_dir: Path, stem: str) -> Path:
    """If audio is an app temp file under recordings_dir, rename to ``{stem}.m4a``."""
    try:
        resolved = audio_path.resolve()
        root = recordings_dir.resolve()
    except OSError:
        return audio_path
    if resolved.parent != root:
        return audio_path
    name = resolved.name
    if not name.startswith("mtg_rec_") or resolved.suffix.lower() != ".m4a":
        return audio_path
    dest = recordings_dir / f"{stem}.m4a"
    if resolved == dest:
        return resolved
    resolved.rename(dest)
    return dest


def write_transcript_txt(transcripts_dir: Path, stem: str, transcript: str) -> Path:
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    path = transcripts_dir / f"{stem}.txt"
    path.write_text(transcript, encoding="utf-8")
    return path


def write_summary_txt(summaries_dir: Path, stem: str, summary: str) -> Path:
    summaries_dir.mkdir(parents=True, exist_ok=True)
    path = summaries_dir / f"{stem}.summary.txt"
    path.write_text(summary, encoding="utf-8")
    return path
