"""Regression guards for offline USB bundle operator scripts."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPT_SCRIPT = REPO_ROOT / "packaging" / "offline" / "scripts" / "accept_offline_bundle.ps1"
USB_ACCEPT_SCRIPT = REPO_ROOT / "packaging" / "offline" / "usb-bundle" / "accept_offline_bundle.ps1"


def _read_accept_script(path: Path) -> str:
    assert path.is_file(), f"missing accept script: {path}"
    return path.read_text(encoding="utf-8")


def test_accept_script_uses_native_command_wrapper_for_huggingface_probe() -> None:
    text = _read_accept_script(ACCEPT_SCRIPT)
    assert "function Invoke-NativeCommand" in text
    hf_idx = text.find("https://huggingface.co")
    assert hf_idx != -1
    window = text[max(0, hf_idx - 220) : hf_idx + 120]
    assert "Invoke-NativeCommand" in window
    assert "curl -fsS" in window


def test_usb_bundle_accept_script_matches_source() -> None:
    source = _read_accept_script(ACCEPT_SCRIPT)
    bundled = _read_accept_script(USB_ACCEPT_SCRIPT)
    assert bundled == source, (
        "packaging/offline/usb-bundle/accept_offline_bundle.ps1 is out of date; "
        "copy from packaging/offline/scripts/ or run build_usb_bundle.ps1"
    )
