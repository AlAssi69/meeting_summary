from __future__ import annotations

import logging
import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

if sys.platform == "win32":
    from meeting_assistant.nvidia_windows_dlls import ensure_nvidia_pip_dll_directories

    ensure_nvidia_pip_dll_directories()

from meeting_assistant import config as _ma_config
from meeting_assistant.logging_setup import configure_logging

configure_logging(_ma_config.TRACE_LEVEL)

# pyannote emits this when TorchCodec native DLLs are absent (common with pip on Windows;
# WhisperX still decodes via FFmpeg). Avoid drowning logs — see README troubleshooting.
warnings.filterwarnings("ignore", category=UserWarning, module=r"pyannote\.audio\.core\.io")


def _warn_if_cuda_requested_but_unavailable() -> None:
    if _ma_config.USE_MOCK_BACKEND:
        return
    try:
        import torch
    except ImportError:
        return
    dev = (_ma_config.WHISPER_DEVICE or "").strip().lower()
    if dev not in ("cuda", "auto"):
        return
    if torch.cuda.is_available():
        return
    logging.getLogger("meeting_assistant.startup").warning(
        "MEETING_ASSISTANT_WHISPER_DEVICE=%r but torch.cuda.is_available() is False — "
        "install a CUDA-enabled PyTorch build (see README / pytorch.org) to use GPU; "
        "WhisperX will use CPU.",
        _ma_config.WHISPER_DEVICE,
    )


_warn_if_cuda_requested_but_unavailable()

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from meeting_assistant.app_context import build_app_facade
from meeting_assistant.ui.emoji_icon import icon_from_emoji


def main() -> None:
    # Native Windows style blocks TextArea background customization; Basic allows it.
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

    qapp = QGuiApplication(sys.argv)
    app_icon = icon_from_emoji("\U0001f399", pixel_size=64)
    qapp.setWindowIcon(app_icon)
    engine = QQmlApplicationEngine()
    facade = build_app_facade(engine)
    # Prevent Python GC from dropping the facade wrapper while QML still references `app`.
    facade.setParent(engine)
    engine.rootContext().setContextProperty("app", facade)
    qml_dir = SRC / "meeting_assistant" / "qml"
    engine.addImportPath(str(qml_dir))
    engine.load(QUrl.fromLocalFile(str(qml_dir / "Main.qml")))
    roots = engine.rootObjects()
    if roots:
        roots[0].setIcon(app_icon)
    if not roots:
        sys.exit(1)
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
