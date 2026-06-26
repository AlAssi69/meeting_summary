#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="/opt/meeting-assistant/src:${PYTHONPATH:-}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
export HF_HUB_DISABLE_TELEMETRY="${HF_HUB_DISABLE_TELEMETRY:-1}"

echo "[entrypoint] Starting WhisperX inference API on port ${WHISPER_API_PORT:-18080}..."

exec python -m uvicorn packaging.offline.services.whisper_api:app \
  --host 0.0.0.0 \
  --port "${WHISPER_API_PORT:-18080}" \
  --app-dir /opt/meeting-assistant
