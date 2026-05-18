"""Register NVIDIA pip wheel DLL directories on Windows for CTranslate2 / CUDA."""

from __future__ import annotations

import logging
import os
import site
import sys

_log = logging.getLogger(__name__)

_registered = False


def ensure_nvidia_pip_dll_directories() -> None:
    """Add site-packages ``nvidia/*/bin`` folders so ``cublas64_12.dll`` et al. load."""
    global _registered
    if _registered:
        return
    if sys.platform != "win32":
        _registered = True
        return

    roots: list[str] = []
    try:
        u = site.getusersitepackages()
        if u:
            roots.append(u)
    except Exception:
        pass
    try:
        roots.extend(site.getsitepackages())
    except Exception:
        pass

    seen: set[str] = set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        nvidia_root = os.path.join(root, "nvidia")
        if not os.path.isdir(nvidia_root):
            continue
        try:
            names = os.listdir(nvidia_root)
        except OSError:
            continue
        for name in names:
            bin_dir = os.path.join(nvidia_root, name, "bin")
            if bin_dir in seen or not os.path.isdir(bin_dir):
                continue
            seen.add(bin_dir)
            try:
                os.add_dll_directory(bin_dir)
            except OSError as e:
                _log.debug("Skipping DLL directory %s: %s", bin_dir, e)

    _registered = True
