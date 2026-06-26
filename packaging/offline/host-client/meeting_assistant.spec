# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Path A Windows host client (no WhisperX/torch)."""

import sys
from pathlib import Path

block_cipher = None

REPO_ROOT = Path(SPECPATH).resolve().parents[2]
SRC = REPO_ROOT / "src"
QML_ROOT = SRC / "meeting_assistant" / "qml"

a = Analysis(
    [str(REPO_ROOT / "main.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        (str(SRC / "meeting_assistant" / "qml"), "meeting_assistant/qml"),
    ],
    hiddenimports=[
        "meeting_assistant",
        "meeting_assistant.adapters.whisperx_http_adapter",
        "meeting_assistant.adapters.ollama_adapter",
        "meeting_assistant.adapters.sqlite_session_repository",
        "meeting_assistant.adapters.whisperx_adapter",
        "meeting_assistant.i18n.ar_catalog",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "whisperx",
        "torch",
        "torchaudio",
        "torchvision",
        "pyannote",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MeetingAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
