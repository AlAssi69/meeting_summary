#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] Meeting Assistant container starting..."

if [[ -z "${MEETING_ASSISTANT_OLLAMA_BASE_URL:-}" ]]; then
  echo "[entrypoint] WARNING: MEETING_ASSISTANT_OLLAMA_BASE_URL is unset."
  echo "[entrypoint]          Set it to the external Ollama endpoint, e.g. http://host.docker.internal:11434"
fi

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo "[entrypoint] WARNING: No DISPLAY/WAYLAND_DISPLAY found."
  echo "[entrypoint]          GUI may fail unless host display sockets/env are mounted."
fi

python3 - <<'PY'
import os
import sys
import urllib.request
import urllib.error

base = os.environ.get("MEETING_ASSISTANT_OLLAMA_BASE_URL", "").rstrip("/")
if not base:
    sys.exit(0)

probe = f"{base}/api/tags"
try:
    with urllib.request.urlopen(probe, timeout=3) as r:
        print(f"[entrypoint] Ollama probe OK: {probe} -> HTTP {r.status}")
except urllib.error.URLError as exc:
    print(f"[entrypoint] WARNING: Ollama probe failed: {probe}: {exc}")
PY

exec python3 /opt/meeting-assistant/main.py
