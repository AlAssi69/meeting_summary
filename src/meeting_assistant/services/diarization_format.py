"""Format WhisperX diarized segments as SRS transcript lines (single source of truth for layout)."""

from __future__ import annotations


def format_timestamp(seconds: float) -> str:
    """Render time as MM:SS, or HH:MM:SS when over one hour (aligned with SRS examples)."""
    s = max(0.0, float(seconds))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(round(s % 60))
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def normalize_segment_speakers(segments: list[dict]) -> None:
    """Map arbitrary diarization labels to SPEAKER_00, SPEAKER_01, … in first-seen order."""
    mapping: dict[str, str] = {}
    n = 0
    for seg in segments:
        raw = seg.get("speaker")
        if raw is None:
            continue
        key = str(raw).strip()
        if not key:
            continue
        if key not in mapping:
            mapping[key] = f"SPEAKER_{n:02d}"
            n += 1
        seg["speaker"] = mapping[key]
    for seg in segments:
        if seg.get("speaker") is None:
            seg["speaker"] = "SPEAKER_00"


def format_diarized_transcript(segments: list[dict]) -> str:
    """One block per segment: SPEAKER_XX [start - end]: text.

    Blocks are separated by a blank line so chat Markdown (paragraph breaks) and
    plain viewers show each speaker/timestamp section on its own line group.
    """
    normalize_segment_speakers(segments)
    lines: list[str] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        label = str(seg.get("speaker") or "SPEAKER_00").strip() or "SPEAKER_00"
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        ts_a = format_timestamp(start)
        ts_b = format_timestamp(end)
        lines.append(f"{label} [{ts_a} - {ts_b}]: {text}")
    out = "\n\n".join(lines).strip()
    return out if out else "(No speech detected)"
