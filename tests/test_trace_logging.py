"""Tests for MEETING_ASSISTANT_TRACE_LEVEL, logging_setup, and trace helpers."""

from __future__ import annotations

import importlib
import logging

import pytest


def test_trace_level_verbose_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEETING_ASSISTANT_TRACE_LEVEL", raising=False)
    monkeypatch.setenv("MEETING_ASSISTANT_VERBOSE", "2")
    try:
        import dotenv

        monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    except ImportError:
        pass
    import meeting_assistant.config as cfg

    importlib.reload(cfg)
    assert cfg.TRACE_LEVEL == 2


def test_trace_level_trace_wins_over_verbose(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEETING_ASSISTANT_TRACE_LEVEL", "1")
    monkeypatch.setenv("MEETING_ASSISTANT_VERBOSE", "3")
    import meeting_assistant.config as cfg

    importlib.reload(cfg)
    assert cfg.TRACE_LEVEL == 1


def test_trace_level_clamped_high(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEETING_ASSISTANT_TRACE_LEVEL", "99")
    import meeting_assistant.config as cfg

    importlib.reload(cfg)
    assert cfg.TRACE_LEVEL == 3


def test_trace_level_invalid_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEETING_ASSISTANT_TRACE_LEVEL", "not-an-int")
    import meeting_assistant.config as cfg

    importlib.reload(cfg)
    assert cfg.TRACE_LEVEL == 0


def test_configure_logging_sets_meeting_assistant_debug_at_level_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEETING_ASSISTANT_TRACE_LEVEL", "3")
    import meeting_assistant.config as cfg

    importlib.reload(cfg)
    from meeting_assistant.logging_setup import configure_logging

    configure_logging(cfg.TRACE_LEVEL)
    assert logging.getLogger("meeting_assistant").level == logging.DEBUG


def test_trace_main_emits_when_level_ge_1(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("MEETING_ASSISTANT_TRACE_LEVEL", "1")
    import meeting_assistant.config as cfg

    importlib.reload(cfg)
    import meeting_assistant.trace as tr

    importlib.reload(tr)
    caplog.set_level(logging.INFO, logger="meeting_assistant.trace")
    tr.trace_main("trace test marker %s", "ok")
    assert "trace test marker ok" in caplog.text


def test_trace_main_silent_at_level_0(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("MEETING_ASSISTANT_TRACE_LEVEL", "0")
    import meeting_assistant.config as cfg

    importlib.reload(cfg)
    import meeting_assistant.trace as tr

    importlib.reload(tr)
    caplog.set_level(logging.INFO, logger="meeting_assistant.trace")
    tr.trace_main("should not appear in caplog at level 0")
    assert "should not appear" not in caplog.text
