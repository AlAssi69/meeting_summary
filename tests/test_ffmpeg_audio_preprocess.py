"""Tests for FFmpeg transcription preprocessing helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from meeting_assistant.services.ffmpeg_audio_preprocess import (
    build_transcription_afilter,
    resolve_ffmpeg_executable,
    run_ffmpeg_transcription_prep,
)


def _ln(
    *,
    enabled: bool = True,
    i: float = -16.0,
    tp: float = -1.5,
    lra: float = 11.0,
) -> dict[str, bool | float]:
    return {
        "loudnorm_enabled": enabled,
        "loudnorm_i": i,
        "loudnorm_tp": tp,
        "loudnorm_lra": lra,
    }


def test_build_transcription_afilter_override_wins() -> None:
    s = build_transcription_afilter(
        override="volume=0.5",
        highpass_hz=80.0,
        threshold_db=-18.0,
        ratio=3.0,
        attack_ms=20.0,
        release_ms=250.0,
        makeup_db=2.0,
        **_ln(),
    )
    assert s == "volume=0.5"


def test_build_transcription_afilter_structured_includes_highpass_compressor_loudnorm() -> None:
    s = build_transcription_afilter(
        override="",
        highpass_hz=100.0,
        threshold_db=-20.0,
        ratio=4.0,
        attack_ms=10.0,
        release_ms=100.0,
        makeup_db=1.0,
        **_ln(i=-16.0, tp=-1.5, lra=11.0),
    )
    assert "highpass=f=100.0" in s
    hp_pos = s.index("highpass")
    comp_pos = s.index("acompressor")
    ln_pos = s.index("loudnorm")
    assert hp_pos < comp_pos < ln_pos
    assert "acompressor=" in s
    assert "threshold=-20.0dB" in s
    assert "ratio=4.0" in s
    assert "attack=10.0" in s
    assert "release=100.0" in s
    assert "makeup=1.0dB" in s
    assert "loudnorm=I=-16.0:TP=-1.5:LRA=11.0" in s


def test_build_transcription_afilter_zero_highpass_omits_highpass() -> None:
    s = build_transcription_afilter(
        override="",
        highpass_hz=0.0,
        threshold_db=-18.0,
        ratio=3.0,
        attack_ms=20.0,
        release_ms=250.0,
        makeup_db=0.0,
        **_ln(),
    )
    assert "highpass" not in s
    assert s.startswith("acompressor=")
    assert "loudnorm=" in s


def test_build_transcription_afilter_loudnorm_disabled_omits_loudnorm() -> None:
    s = build_transcription_afilter(
        override="",
        highpass_hz=80.0,
        threshold_db=-18.0,
        ratio=3.0,
        attack_ms=20.0,
        release_ms=250.0,
        makeup_db=0.0,
        **_ln(enabled=False),
    )
    assert "loudnorm" not in s


def test_resolve_ffmpeg_executable_env_path_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = tmp_path / "custom_ffmpeg.exe"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setattr("meeting_assistant.config.FFMPEG_PATH", str(fake))
    resolved = resolve_ffmpeg_executable()
    assert resolved == fake.resolve()


def test_run_ffmpeg_transcription_prep_success(tmp_path: Path) -> None:
    inp = tmp_path / "in.wav"
    inp.write_bytes(b"fake")
    out = tmp_path / "out.wav"
    fake_ff = tmp_path / "ffmpeg_sidecar.exe"
    fake_ff.write_bytes(b"")
    mock_cp = MagicMock()
    mock_cp.returncode = 0
    mock_cp.stderr = ""
    with (
        patch(
            "meeting_assistant.services.ffmpeg_audio_preprocess.resolve_ffmpeg_executable",
            return_value=fake_ff,
        ),
        patch("meeting_assistant.services.ffmpeg_audio_preprocess.subprocess.run", return_value=mock_cp) as run,
    ):
        run_ffmpeg_transcription_prep(
            inp,
            out,
            afilter="anull",
            sample_rate=16000,
            timeout_sec=60.0,
        )
        run.assert_called_once()
        args, kwargs = run.call_args
        argv = args[0]
        assert argv[0] == str(fake_ff)
        assert "-i" in argv
        assert str(inp) in argv
        assert "-af" in argv
        assert "anull" in argv
        assert "-ar" in argv and "16000" in argv
        assert "-ac" in argv and "1" in argv
        assert str(out) in argv


def test_run_ffmpeg_transcription_prep_no_executable_raises(tmp_path: Path) -> None:
    inp = tmp_path / "in.wav"
    inp.write_bytes(b"fake")
    out = tmp_path / "out.wav"
    with patch(
        "meeting_assistant.services.ffmpeg_audio_preprocess.resolve_ffmpeg_executable",
        return_value=None,
    ):
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            run_ffmpeg_transcription_prep(
                inp,
                out,
                afilter="anull",
                sample_rate=16000,
                timeout_sec=60.0,
            )


def test_run_ffmpeg_transcription_prep_failure_raises(tmp_path: Path) -> None:
    inp = tmp_path / "in.wav"
    inp.write_bytes(b"fake")
    out = tmp_path / "out.wav"
    fake_ff = tmp_path / "ffmpeg.exe"
    fake_ff.write_bytes(b"")
    mock_cp = MagicMock()
    mock_cp.returncode = 1
    mock_cp.stderr = "some error from ffmpeg" * 50
    with (
        patch(
            "meeting_assistant.services.ffmpeg_audio_preprocess.resolve_ffmpeg_executable",
            return_value=fake_ff,
        ),
        patch(
            "meeting_assistant.services.ffmpeg_audio_preprocess.subprocess.run",
            return_value=mock_cp,
        ),
    ):
        with pytest.raises(RuntimeError, match="FFmpeg audio preprocessing failed"):
            run_ffmpeg_transcription_prep(
                inp,
                out,
                afilter="anull",
                sample_rate=16000,
                timeout_sec=60.0,
            )


def test_run_ffmpeg_transcription_prep_timeout(tmp_path: Path) -> None:
    inp = tmp_path / "in.wav"
    inp.write_bytes(b"fake")
    out = tmp_path / "out.wav"
    fake_ff = tmp_path / "ffmpeg.exe"
    fake_ff.write_bytes(b"")
    import subprocess as sp

    with (
        patch(
            "meeting_assistant.services.ffmpeg_audio_preprocess.resolve_ffmpeg_executable",
            return_value=fake_ff,
        ),
        patch(
            "meeting_assistant.services.ffmpeg_audio_preprocess.subprocess.run",
            side_effect=sp.TimeoutExpired(cmd="ffmpeg", timeout=1),
        ),
    ):
        with pytest.raises(RuntimeError, match="timed out"):
            run_ffmpeg_transcription_prep(
                inp,
                out,
                afilter="anull",
                sample_rate=16000,
                timeout_sec=1.0,
            )


def test_ffmpeg_preparer_deletes_temp_after_context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from meeting_assistant.services.transcription_audio_prep import (
        FfmpegWavTranscriptionAudioPreparer,
    )

    src = tmp_path / "source.wav"
    src.write_bytes(b"x")
    monkeypatch.setattr("meeting_assistant.config.AUDIO_PREP_KEEP_TEMP", False)
    monkeypatch.setattr("meeting_assistant.config.AUDIO_PREP_OUTPUT_SAMPLE_RATE", 16000)
    monkeypatch.setattr("meeting_assistant.config.AUDIO_PREP_FFMPEG_TIMEOUT_SEC", 60.0)
    monkeypatch.setattr(
        "meeting_assistant.services.transcription_audio_prep.build_transcription_afilter_from_config",
        lambda: "anull",
    )
    with patch(
        "meeting_assistant.services.transcription_audio_prep.run_ffmpeg_transcription_prep",
    ) as rf:
        prep = FfmpegWavTranscriptionAudioPreparer()
        out_path: Path | None = None
        with prep.prepare(src) as p:
            out_path = p
            assert p.suffix == ".wav"
        assert out_path is not None
        rf.assert_called_once()
        assert not out_path.exists()
