# Offline USB Bundle (Path A — PyInstaller + Headless WhisperX + Containerized Ollama)

Air-gapped delivery for **Meeting Assistant** on Windows 10/11: native desktop GUI on the host, WhisperX and Ollama in Docker. The only target prerequisite is **Docker Desktop**.

## Architecture

| Component | Runs on |
|-----------|---------|
| `MeetingAssistant.exe` (PySide6/QML, mic, SQLite, outputs) | Windows host |
| WhisperX inference API (`large-v3-turbo`, align `ar`) | Docker container `:18080` |
| Ollama summarization (model baked in) | Docker container `:11434` |

Whisper models are **baked into both** GPU and CPU images, and the Ollama model is **baked into the Ollama image**, at build time. No Hugging Face, pip, or Ollama downloads on the target machine.

GPU is **best-effort**: the installer uses an NVIDIA GPU when present and auto-falls back to CPU otherwise.

All packaging lives under [`packaging/offline/`](../packaging/offline/) — the legacy `docker/` tree is **not** used.

## Prerequisites

### Build machine (online)

- Windows 10/11 with Docker Desktop (BuildKit enabled)
- Python 3.12 (for PyInstaller host client)
- NVIDIA Container Toolkit (optional; for validating the GPU image locally)
- **80 GB+** free disk (three image tars + models baked in)

### Target machine (offline)

- Windows 10/11
- **Docker Desktop** (Hyper-V backend is OK; GPU passthrough requires the WSL2 backend + NVIDIA Container Toolkit)
- No internet after USB copy
- Nothing else — Ollama and its model ship inside the bundle

## Build and export (online)

From the repository root:

```powershell
.\packaging\offline\scripts\build_usb_bundle.ps1 -OutputDir .\packaging\offline\usb-bundle
```

This produces:

| Artifact | Purpose |
|----------|---------|
| `images/meeting-assistant-gpu-bundle.tar` | GPU Whisper inference image |
| `images/meeting-assistant-cpu-bundle.tar` | CPU Whisper inference image |
| `images/meeting-assistant-ollama-bundle.tar` | Ollama image with model baked in |
| `bin/MeetingAssistant.exe` | Host desktop client |
| `compose/compose.yml`, `compose/compose.gpu.yml` | Base + GPU-override Compose files |
| `.env.bundle` | Host + container environment |
| `install_from_usb.ps1` | Load images, probe GPU, start inference |
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

- `docker load` all three image tars (Whisper GPU, Whisper CPU, Ollama)
- Probe the GPU with `docker run --rm --gpus all <gpu-image> nvidia-smi`
- If GPU is available: start `docker compose -f compose.yml -f compose.gpu.yml up -d` and health-check Whisper + Ollama
- Otherwise (or on GPU failure): start `docker compose -f compose.yml up -d` (CPU)
- Create persistent host directories:
  - `{bundle}\data\` → SQLite (`MEETING_ASSISTANT_DATA_DIR`)
  - `{bundle}\meeting_outputs\` → recordings, transcripts, summaries

Force CPU with `.\install_from_usb.ps1 -ForceCpu`.

4. Launch the desktop app:

```powershell
.\launch_host_client.ps1
```

Bypass Windows SmartScreen if prompted (unsigned `.exe`).

## Ollama

Ollama now runs **inside the bundle** as a container on `http://127.0.0.1:11434`, with the
model baked into the image at build time. At build the image pulls the base model
`gemma4:e4b`, then derives a long-context variant `gemma4:e4b128k` (`num_ctx = 131072`,
~128k tokens) via `ollama create` + a Modelfile. The application uses the derived
`gemma4:e4b128k`. The host client talks to it directly. Default in `.env.bundle`:

```env
MEETING_ASSISTANT_OLLAMA_BASE_URL=http://127.0.0.1:11434
MEETING_ASSISTANT_OLLAMA_MODEL=gemma4:e4b128k
```

To change models or context length, rebuild with `-OllamaBaseModel <tag>`, `-OllamaModel
<tag>`, and/or `-OllamaNumCtx <tokens>` (the base tag must be pullable on the build machine).

## GPU → CPU fallback

Two tiers:

1. **Install-level** (`install_from_usb.ps1`): GPU probe + GPU compose health check → CPU compose
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
```

### Manual checklist

- [ ] `http://127.0.0.1:18080/health` returns `{"status":"ok"}`
- [ ] `http://127.0.0.1:18080/v1/status` shows `model_ready: true`
- [ ] `http://127.0.0.1:11434/api/tags` lists the configured Ollama model
- [ ] Transcription completes on imported audio with no network
- [ ] Summary returns from the containerized Ollama
- [ ] SQLite and outputs persist under `{bundle}\data` and `{bundle}\meeting_outputs`
- [ ] Mic recording works in `MeetingAssistant.exe`

## Size guidance

With `large-v3-turbo` baked into **both** Whisper images plus the Ollama model:

- Plan **80 GB+** USB capacity
- Each Whisper image tar is typically **10–25 GB**; the Ollama image depends on the chosen model

## Troubleshooting

| Symptom | Action |
|---------|--------|
| GPU profile fails immediately | Expected on Hyper-V; installer falls back to CPU automatically |
| `model_ready: false` | Re-run `install_from_usb.ps1`; check `docker logs meeting-assistant-whisper` |
| Whisper API unreachable | Confirm container is up: `docker ps` |
| Ollama model missing | Rebuild bundle with a valid `-OllamaModel` tag; check `docker logs meeting-assistant-ollama` |
| Summarization fails | Verify `http://127.0.0.1:11434/api/tags` and the model name in `.env.bundle` |
| SmartScreen blocks `.exe` | Click “More info” → “Run anyway” |

Further detail: [`packaging/offline/README.md`](../packaging/offline/README.md).
