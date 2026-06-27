#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="/opt/meeting-assistant/src:${PYTHONPATH:-}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
export HF_HUB_DISABLE_TELEMETRY="${HF_HUB_DISABLE_TELEMETRY:-1}"

# --- GPU diagnostic (best-effort; never fatal) ---
# Helps confirm whether the NVIDIA driver/Container Toolkit is wired through to this
# container. On CPU-only hosts these simply report "unavailable" and the WhisperX engine
# falls back to CPU at runtime.
echo "[entrypoint] Requested WhisperX device: ${MEETING_ASSISTANT_WHISPER_DEVICE:-auto}"
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "[entrypoint] nvidia-smi:"
  nvidia-smi || echo "[entrypoint] nvidia-smi present but failed (no GPU passthrough?)"
else
  echo "[entrypoint] nvidia-smi not found (CPU-only container or no NVIDIA Container Toolkit)."
fi
python - <<'PY' || true
try:
    import torch
    print(f"[entrypoint] torch={torch.__version__} cuda_available={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"[entrypoint] cuda_device={torch.cuda.get_device_name(0)}")
except Exception as exc:  # noqa: BLE001
    print(f"[entrypoint] torch CUDA probe failed: {exc}")
PY

echo "[entrypoint] Starting WhisperX inference API on port ${WHISPER_API_PORT:-18080}..."

exec python -m uvicorn whisper_api:app \
  --host 0.0.0.0 \
  --port "${WHISPER_API_PORT:-18080}" \
  --app-dir /opt/meeting-assistant/packaging/offline/services
