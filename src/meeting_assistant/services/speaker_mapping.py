"""Extract diarized speaker keys and apply user display-name mapping (pure functions)."""

from __future__ import annotations

import re

# Matches WhisperX / format_diarized_transcript labels at line start.
_SPEAKER_LINE_START = re.compile(r"^SPEAKER_(\d{2})\b", re.MULTILINE)
_SPEAKER_TOKEN = re.compile(r"^(SPEAKER_\d{2})\b")
# First line of a diarized block: SPEAKER_00 [MM:SS - MM:SS]: or [HH:MM:SS - HH:MM:SS]:
_DIARIZED_BLOCK_HEADER = re.compile(
    r"^(SPEAKER_\d{2})\s+\[([^\]]+?)\s*-\s*([^\]]+?)\]:\s*",
)


def extract_speaker_keys(text: str) -> list[str]:
    """Return SPEAKER_00, SPEAKER_01, … in order of first appearance in ``text``."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _SPEAKER_LINE_START.finditer(text or ""):
        key = f"SPEAKER_{m.group(1)}"
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def apply_speaker_mapping(text: str, mapping: dict[str, str]) -> str:
    """Replace line-initial ``SPEAKER_XX`` tokens with user names; unknown keys unchanged."""

    def repl_line(line: str) -> str:
        m = _SPEAKER_TOKEN.match(line)
        if not m:
            return line
        key = m.group(1)
        display = (mapping.get(key) or key).strip() or key
        return display + line[m.end(1) :]

    lines = (text or "").splitlines()
    return "\n".join(repl_line(line) for line in lines)


def parse_timestamp_to_seconds(ts: str) -> float:
    """Parse ``MM:SS`` or ``HH:MM:SS`` (as emitted by ``format_diarized_transcript``) to seconds."""
    parts = (ts or "").strip().split(":")
    if len(parts) == 2:
        return float(int(parts[0]) * 60 + int(parts[1]))
    if len(parts) == 3:
        return float(
            int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]),
        )
    raise ValueError(f"unsupported timestamp: {ts!r}")


def first_time_range_sec_by_speaker(text: str) -> dict[str, tuple[float, float]]:
    """For each ``SPEAKER_XX``, return ``(start_sec, end_sec)`` of its first diarized block.

    Blocks are separated by blank lines (same layout as ``format_diarized_transcript``).
    Only the first line of each block is considered for the header pattern.
    """
    out: dict[str, tuple[float, float]] = {}
    for block in (text or "").split("\n\n"):
        chunk = block.strip()
        if not chunk:
            continue
        first_line = chunk.splitlines()[0]
        m = _DIARIZED_BLOCK_HEADER.match(first_line)
        if not m:
            continue
        key = m.group(1)
        if key in out:
            continue
        try:
            start = parse_timestamp_to_seconds(m.group(2))
            end = parse_timestamp_to_seconds(m.group(3))
        except ValueError:
            continue
        if end < start:
            start, end = end, start
        out[key] = (start, end)
    return out
