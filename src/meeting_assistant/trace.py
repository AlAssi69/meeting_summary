"""Gated trace messages for MEETING_ASSISTANT_TRACE_LEVEL (1=main, 2=detail, 3=verbose)."""

from __future__ import annotations

import logging

from meeting_assistant import config

_log = logging.getLogger("meeting_assistant.trace")


def trace_main(msg: str, *args: object, **kwargs: object) -> None:
    if config.TRACE_LEVEL >= 1:
        _log.info(msg, *args, **kwargs)


def trace_step(msg: str, *args: object, **kwargs: object) -> None:
    if config.TRACE_LEVEL >= 2:
        _log.info(msg, *args, **kwargs)


def trace_dump(msg: str, *args: object, **kwargs: object) -> None:
    if config.TRACE_LEVEL >= 3:
        _log.debug(msg, *args, **kwargs)
