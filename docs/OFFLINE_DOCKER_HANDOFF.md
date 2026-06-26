# Offline USB Bundle (Path A — PyInstaller + Headless WhisperX)

Air-gapped delivery for **Meeting Assistant** on Windows 10/11: native desktop GUI on the host, WhisperX in Docker, Ollama on the host.

## Architecture

| Component | Runs on |
|-----------|---------|
| `MeetingAssistant.exe` (PySide6/QML, mic, SQLite, outputs) | Windows host |
| WhisperX inference API (`large-v3-turbo`, align `ar`) | Docker container `:18080` |
| Ollama summarization | Windows host (`http://127.0.0.1:11434`) |

Models are **baked into both** GPU and CPU images at build time. No Hugging Face or pip downloads on the target machine.

All packaging lives under [`packaging/offline/`](../packaging/offline/) — the legacy `docker/` tree is **not** used.

## Prerequisites

### Build machine (online)

- Windows 10/11 with Docker Desktop
- Python 3.12 (for PyInstaller host client)
- NVIDIA Container Toolkit (optional; for validating GPU image locally)
- **64 GB+** free disk (two image tars + models baked into both)

### Target machine (offline)

- Windows 10/11
- Docker Desktop (Hyper-V backend is OK; GPU passthrough may be unavailable)
- Ollama installed natively with model already pulled (e.g. `gemma4:e4b128k`)
- No internet after USB copy

## Build and export (online)

From the repository root:

```powershell
.\packaging\offline\scripts\build_usb_bundle.ps1 -OutputDir .\packaging\offline\usb-bundle
```

This produces:

| Artifact | Purpose |
|----------|---------|
| `images/meeting-assistant-gpu-bundle.tar` | GPU inference image |
| `images/meeting-assistant-cpu-bundle.tar` | CPU inference image |
| `bin/MeetingAssistant.exe` | Host desktop client |
| `compose/compose.gpu.yml`, `compose/compose.cpu.yml` | Docker Compose profiles |
| `.env.bundle` | Host + container environment |
| `install_from_usb.ps1` | Load images, start inference |
| `launch_host_client.ps1` | Open desktop app |
| `RUNBOOK.txt` | Operator instructions (copy of packaging README) |

Copy the **entire** `usb-bundle` folder to USB.

## Deploy on target (offline)

1. Copy the bundle from USB to local disk (e.g. `C:\MeetingAssistantBundle`).
2. Open **`RUNBOOK.txt`** next to the install script for quick reference.
3. Run:

```powershell
cd C:\MeetingAssistantBundle
.\install_from_usb.ps1
```

`install_from_usb.ps1` will:

- `docker load` both image tars
- Try the **GPU** compose profile and health-check `http://127.0.0.1:18080/health`
- On failure (common on Hyper-V without GPU passthrough), tear down GPU and start **CPU**
- Create persistent host directories:
  - `{bundle}\data\` → SQLite (`MEETING_ASSISTANT_DATA_DIR`)
  - `{bundle}\meeting_outputs\` → recordings, transcripts, summaries

4. Launch the desktop app:

```powershell
.\launch_host_client.ps1
```

Bypass Windows SmartScreen if prompted (unsigned `.exe`).

## Ollama

The host client talks to Ollama directly. Default in `.env.bundle`:

```env
MEETING_ASSISTANT_OLLAMA_BASE_URL=http://127.0.0.1:11434
MEETING_ASSISTANT_OLLAMA_MODEL=gemma4:e4b128k
```

Ensure Ollama is running and the model is already pulled before summarizing.

## GPU → CPU fallback

Two tiers:

1. **Compose-level** (`install_from_usb.ps1`): GPU profile health check → CPU profile
2. **Runtime** (inside container): `whisperx_engine` CUDA → CPU if driver/load fails

Active profile is recorded in `{bundle}\.active_profile` (`gpu` or `cpu`).

## Offline acceptance

After `install_from_usb.ps1`, run:

```powershell
.\accept_offline_bundle.ps1
```

Optional flags:

```powershell
# Include a short test audio file for end-to-end transcribe
.\accept_offline_bundle.ps1 -TestAudioPath .\sample.wav

# Also probe Ollama /api/tags
.\accept_offline_bundle.ps1 -CheckOllama
```

### Manual checklist

- [ ] `http://127.0.0.1:18080/health` returns `{"status":"ok"}`
- [ ] `http://127.0.0.1:18080/v1/status` shows `model_ready: true`
- [ ] Transcription completes on imported audio with no network
- [ ] Summary reaches host Ollama
- [ ] SQLite and outputs persist under `{bundle}\data` and `{bundle}\meeting_outputs`
- [ ] Mic recording works in `MeetingAssistant.exe`

## Size guidance

With `large-v3-turbo` baked into **both** images:

- Plan **64 GB+** USB capacity
- Each image tar is typically **10–25 GB** depending on compression and layer deduplication

## Troubleshooting

| Symptom | Action |
|---------|--------|
| GPU profile fails immediately | Expected on Hyper-V; CPU profile should start automatically |
| `model_ready: false` | Re-run `install_from_usb.ps1`; check `docker logs meeting-assistant-whisper-cpu` |
| Whisper API unreachable | Confirm container is up: `docker ps` |
| Summarization fails | Verify Ollama at `http://127.0.0.1:11434` and model name in `.env.bundle` |
| SmartScreen blocks `.exe` | Click “More info” → “Run anyway” |

Further detail: [`packaging/offline/README.md`](../packaging/offline/README.md).
