"""Post-ASR segment filtering for WhisperX (batched path does not apply faster-whisper segment gates)."""

from __future__ import annotations

import zlib


def _compression_ratio(text: str) -> float:
    """Same ratio faster-whisper uses to detect repetitive hallucinations."""
    text_bytes = text.encode("utf-8")
    return len(text_bytes) / len(zlib.compress(text_bytes))


def filter_whisperx_asr_segments(
    segments: list[dict],
    *,
    compression_ratio_threshold: float,
    compression_min_chars: int,
    min_avg_logprob: float | None,
) -> list[dict]:
    """Drop segments that look like hallucinations (repetitive text) or are very low confidence.

    Mirrors faster-whisper's compression_ratio check for long strings. Short segments skip the
    compression test to avoid false drops on brief phrases.
    """
    out: list[dict] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        if min_avg_logprob is not None and "avg_logprob" in seg:
            try:
                ap = float(seg["avg_logprob"])
            except (TypeError, ValueError):
                ap = None
            if ap is not None and ap < min_avg_logprob:
                continue
        if len(text) >= compression_min_chars:
            if _compression_ratio(text) > compression_ratio_threshold:
                continue
        out.append(seg)
    return out
