import importlib

import pytest


def test_whisper_compute_type_candidates_for_device_gpu_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEETING_ASSISTANT_WHISPER_COMPUTE_TYPES", raising=False)
    from meeting_assistant import config

    assert config.whisper_compute_type_candidates_for_device("cuda") == (
        "float16",
        "int16",
        "int8",
        "default",
    )


def test_whisper_compute_type_candidates_for_device_cpu_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEETING_ASSISTANT_WHISPER_COMPUTE_TYPES", raising=False)
    from meeting_assistant import config

    assert config.whisper_compute_type_candidates_for_device("cpu") == ("int16", "int8", "default")


def test_whisper_compute_type_candidates_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEETING_ASSISTANT_WHISPER_COMPUTE_TYPES", "float32, int8")
    from meeting_assistant import config

    assert config.whisper_compute_type_candidates_for_device("cuda") == ("float32", "int8")
    assert config.whisper_compute_type_candidates_for_device("cpu") == ("float32", "int8")


def test_whisper_beam_default_is_seven(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEETING_ASSISTANT_WHISPER_BEAM_SIZE", raising=False)
    import meeting_assistant.config as cfg

    importlib.reload(cfg)
    assert cfg.WHISPER_BEAM_SIZE == 7
