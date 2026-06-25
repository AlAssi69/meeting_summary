# Offline Docker Handoff (Windows 11)

This guide packages the app for USB transfer, then runs it on another laptop without internet downloads.

## Scope

- Keep Ollama external (already running on host or another device).
- Keep GUI behavior (Qt window) from the container.
- Support both GPU and CPU profiles.

## Prerequisites on target laptop

- Windows 11
- Docker Desktop installed
- NVIDIA driver installed for GPU profile (CPU profile does not require this)
- No internet required after `docker load`

## Build and export (online source machine)

From the repository root:

```powershell
.\docker\export_offline.ps1 -OutputDir .\docker\offline-bundle
```

This builds:

- `meeting-assistant:gpu-offline`
- `meeting-assistant:cpu-offline`

And exports:

- `meeting-assistant-gpu-offline.tar`
- `meeting-assistant-cpu-offline.tar`
- `compose.offline.yml`
- `.env.offline`
- `import_and_run_offline.ps1`

## Copy to USB

Copy the full `docker/offline-bundle` folder to USB.

## Import and run on target (offline)

1. Copy bundle folder from USB to local disk.
2. Edit `.env.offline` and set Ollama endpoint.
3. Run one profile:

```powershell
# GPU profile (recommended when NVIDIA is available)
.\import_and_run_offline.ps1 -BundleDir . -Profile gpu

# CPU profile fallback
.\import_and_run_offline.ps1 -BundleDir . -Profile cpu
```

## Ollama endpoint patterns

Set `MEETING_ASSISTANT_OLLAMA_BASE_URL` in `.env.offline`:

- Ollama on same laptop host: `http://host.docker.internal:11434`
- Ollama on another LAN device: `http://192.168.1.50:11434`
- Ollama on named host: `http://ollama-workstation:11434`

## Notes about GUI forwarding

The compose file mounts WSLg/X11 related paths for Linux GUI forwarding from container to Windows desktop. If the window does not appear:

- Verify Docker Desktop uses WSL2 backend.
- Keep `/mnt/wslg` and `/tmp/.X11-unix` mounts intact.
- Try CPU profile first to separate GUI issues from CUDA issues.

## Validation checklist (offline acceptance)

- App container starts and opens the GUI window.
- Transcript can be generated without downloading model files.
- Summary request reaches external Ollama endpoint.
- CPU profile works when GPU profile is unavailable.
- No required runtime internet calls after image import.

## Size guidance

Typical ranges (depends on model choices):

- CPU image tar: 6-12 GB
- GPU image tar: 10-20+ GB
- Plan USB capacity for both images plus working margin (32-64 GB recommended).
