# Offline USB bundle (Path A) — PyInstaller host client + headless WhisperX + containerized Ollama

Air-gapped delivery for **Meeting Assistant**: native Windows GUI (mic + SQLite on host),
WhisperX and Ollama in Docker. The only prerequisite on the target machine is **Docker Desktop**.

## Architecture

| Component | Where it runs |
|-----------|----------------|
| PySide6/QML GUI, mic, SQLite, meeting outputs | `MeetingAssistant.exe` on Windows host |
| WhisperX ASR + alignment (`large-v3-turbo`, align `ar`) | Docker container `:18080` |
| Summarization (Ollama, model baked in) | Docker container `:11434` |

Whisper models are **baked into both** GPU and CPU images, and the Ollama model is **baked
into the Ollama image**, at build time. No Hub/pip/Ollama downloads at runtime.

The Ollama image pulls a base model (`gemma4:e4b`) and then derives a long-context variant
`gemma4:e4b128k` (`num_ctx = 131072`, ~128k tokens) via `ollama create` + a Modelfile. The
application uses the derived `gemma4:e4b128k`.

GPU is **best-effort**: the installer probes for an NVIDIA GPU and uses it when available,
otherwise everything runs on CPU.

## Build machine (online)

Requirements: Docker Desktop (with BuildKit), Python 3.12, ~80 GB free disk, and internet
access (to pull base images, pip wheels, Whisper weights, and the Ollama model).

Steps:

1. Open PowerShell at the repository root.
2. (Optional) Sign in / verify the base models are pullable. The Ollama image pulls
   `gemma4:e4b`; confirm `ollama pull gemma4:e4b` works on this machine (or pass a different
   `-OllamaBaseModel`).
3. Build all three images, the host client, and assemble the bundle:

```powershell
.\packaging\offline\scripts\build_usb_bundle.ps1 -OutputDir .\packaging\offline\usb-bundle
```

   Optional build args: `-WhisperModel`, `-WhisperAlignLanguage`, `-OllamaBaseModel`,
   `-OllamaModel`, `-OllamaNumCtx`, `-SkipHostClient`. Example to change the summary model:

```powershell
.\packaging\offline\scripts\build_usb_bundle.ps1 -OllamaBaseModel gemma4:e4b -OllamaModel gemma4:e4b128k -OllamaNumCtx 131072
```

4. Confirm the output folder `packaging/offline/usb-bundle/` contains:
   - `images/meeting-assistant-gpu-bundle.tar`
   - `images/meeting-assistant-cpu-bundle.tar`
   - `images/meeting-assistant-ollama-bundle.tar`
   - `bin/MeetingAssistant.exe`
   - `compose/compose.yml`, `compose/compose.gpu.yml`
   - `.env.bundle`
   - `install_from_usb.ps1`, `launch_host_client.ps1`, `accept_offline_bundle.ps1`
   - `RUNBOOK.txt` (this file, copied to bundle root for end users)
5. Copy the **entire** `usb-bundle` folder to the USB drive.

## Target machine (offline)

Prerequisite: **Docker Desktop only** (Hyper-V or WSL2 backend). GPU acceleration also
requires the WSL2 backend with the NVIDIA Container Toolkit + driver; otherwise CPU is used.

Steps:

1. Copy bundle from USB to local disk (e.g. `C:\MeetingAssistantBundle`).
2. Read **`RUNBOOK.txt`** in the bundle folder.
3. Run:

```powershell
cd C:\MeetingAssistantBundle
.\install_from_usb.ps1
```

This loads all images, probes the GPU (`docker run --gpus all ... nvidia-smi`), starts the
**GPU** profile when available, health-checks Whisper (`:18080/health`) and Ollama
(`:11434/api/tags`), and **falls back to CPU** automatically when the GPU is unavailable or
the GPU profile fails. Force CPU with `.\install_from_usb.ps1 -ForceCpu`.

4. Validate the bundle:

```powershell
.\accept_offline_bundle.ps1
```

Optional: `.\accept_offline_bundle.ps1 -TestAudioPath .\sample.wav`

5. Launch the desktop app:

```powershell
.\launch_host_client.ps1
```

Bypass SmartScreen if prompted (unsigned `.exe`).

## Persistent data (host)

`install_from_usb.ps1` enforces:

| Path | Purpose |
|------|---------|
| `{bundle}\data\` | SQLite (`meetings.db`) via `MEETING_ASSISTANT_DATA_DIR` |
| `{bundle}\meeting_outputs\` | Recordings, transcripts, summaries via `MEETING_ASSISTANT_OUTPUT_ROOT` |

The Ollama model blobs persist in the `meeting_assistant_ollama` Docker volume across restarts.

## Environment (`.env.bundle`)

| Variable | Default |
|----------|---------|
| `MEETING_ASSISTANT_WHISPER_API_URL` | `http://127.0.0.1:18080` |
| `MEETING_ASSISTANT_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` |
| `MEETING_ASSISTANT_OLLAMA_MODEL` | `gemma4:e4b128k` (derived 128k-context model the app uses) |
| `MEETING_ASSISTANT_WHISPER_MODEL` | `large-v3-turbo` |
| `MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE` | `ar` |
| `MEETING_ASSISTANT_SPEAKER_DIARIZATION` | `0` |

## Acceptance checklist

Run `.\accept_offline_bundle.ps1` after install, or verify manually:

- [ ] `install_from_usb.ps1` completes; `.active_profile` is `gpu` or `cpu`
- [ ] `accept_offline_bundle.ps1` exits 0
- [ ] `http://127.0.0.1:18080/v1/status` shows `model_ready: true`
- [ ] `http://127.0.0.1:11434/api/tags` lists the configured Ollama model
- [ ] `MeetingAssistant.exe` opens; mic record + import work
- [ ] Transcription completes with no network
- [ ] Summary returns from the containerized Ollama
- [ ] Data persists in `{bundle}\data` and `{bundle}\meeting_outputs` after restart

## Build host client only

```powershell
.\packaging\offline\host-client\build_host_client.ps1
```

## Build inference images only

```powershell
$env:DOCKER_BUILDKIT = "1"
docker build -f packaging/offline/images/Dockerfile.gpu -t meeting-assistant:gpu-bundle .
docker build -f packaging/offline/images/Dockerfile.cpu -t meeting-assistant:cpu-bundle .
docker build -f packaging/offline/images/Dockerfile.ollama `
  --build-arg OLLAMA_BASE_MODEL=gemma4:e4b `
  --build-arg OLLAMA_MODEL=gemma4:e4b128k `
  --build-arg OLLAMA_NUM_CTX=131072 `
  -t meeting-assistant:ollama-bundle .
```
