"""Central logging configuration (see MEETING_ASSISTANT_TRACE_LEVEL)."""

from __future__ import annotations

import logging
import sys

_NOISY_THIRD_PARTY = (
    "torch",
    "transformers",
    "httpx",
    "httpcore",
    "urllib3",
    "lightning",
    "lightning_fabric",
    "whisperx",
)


def configure_logging(trace_level: int) -> None:
    """Configure root and ``meeting_assistant`` loggers for stderr.

    ``trace_level`` 0–2: root INFO, ``meeting_assistant`` INFO (same baseline as before).
    Level 3: root DEBUG, ``meeting_assistant`` DEBUG; third-party loggers capped at WARNING.
    """
    tl = max(0, min(3, trace_level))
    root_level = logging.DEBUG if tl >= 3 else logging.INFO
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    kwargs: dict = {
        "level": root_level,
        "format": fmt,
        "datefmt": datefmt,
    }
    if sys.version_info >= (3, 8):
        kwargs["force"] = True
    logging.basicConfig(**kwargs)

    ma = logging.getLogger("meeting_assistant")
    ma.setLevel(logging.DEBUG if tl >= 3 else logging.INFO)

    # Short name in log column; banners + "| AUDIO-PREP |" lines are easy to spot when scrolling.
    logging.getLogger("meeting_assistant.audio_prep").setLevel(logging.DEBUG if tl >= 3 else logging.INFO)

    if tl >= 3:
        for name in _NOISY_THIRD_PARTY:
            logging.getLogger(name).setLevel(logging.WARNING)
