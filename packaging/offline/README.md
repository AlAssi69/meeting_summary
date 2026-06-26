# Offline USB bundle (Path A) — PyInstaller host client + headless WhisperX containers

Air-gapped delivery for **Meeting Assistant**: native Windows GUI (mic + SQLite on host), WhisperX in Docker, Ollama on the host at `http://127.0.0.1:11434`.

## Architecture

| Component | Where it runs |
|-----------|----------------|
| PySide6/QML GUI, mic, SQLite, meeting outputs | `MeetingAssistant.exe` on Windows host |
| WhisperX ASR + alignment (`large-v3-turbo`, align `ar`) | Docker container `:18080` |
| Summarization | Host Ollama (not containerized) |

Models are **baked into both** GPU and CPU images at build time. No Hub downloads at runtime.

## Build machine (online)

Requirements: Docker Desktop, Python 3.12, ~64 GB free disk.

From repository root:

```powershell
.\packaging\offline\scripts\build_usb_bundle.ps1 -OutputDir .\packaging\offline\usb-bundle
```

Produces `packaging/offline/usb-bundle/`:

- `images/meeting-assistant-gpu-bundle.tar`
- `images/meeting-assistant-cpu-bundle.tar`
- `bin/MeetingAssistant.exe`
- `compose/compose.gpu.yml`, `compose/compose.cpu.yml`
- `.env.bundle`
- `install_from_usb.ps1`, `launch_host_client.ps1`, `accept_offline_bundle.ps1`
- `RUNBOOK.txt` (this file, copied to bundle root for end users)

Copy the **entire folder** to USB.

## Target machine (offline)

Prerequisites:

- Windows 10/11
- Docker Desktop (Hyper-V backend is OK; GPU passthrough may be unavailable)
- Ollama running natively with model already pulled (e.g. `gemma4:e4b128k`)

Steps:

1. Copy bundle from USB to local disk (e.g. `C:\MeetingAssistantBundle`).
2. Read **`RUNBOOK.txt`** in the bundle folder.
3. Run:

```powershell
cd C:\MeetingAssistantBundle
.\install_from_usb.ps1
```

This loads images, tries **GPU** compose, waits for `http://127.0.0.1:18080/health`, and **falls back to CPU** when GPU reservation fails (expected on Hyper-V without NVIDIA Container Toolkit).

4. Validate the bundle:

```powershell
.\accept_offline_bundle.ps1
```

Optional: `.\accept_offline_bundle.ps1 -TestAudioPath .\sample.wav -CheckOllama`

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

All session artifacts and processed audio paths referenced from SQLite remain under these directories across restarts.

## Environment (`.env.bundle`)

| Variable | Default |
|----------|---------|
| `MEETING_ASSISTANT_WHISPER_API_URL` | `http://127.0.0.1:18080` |
| `MEETING_ASSISTANT_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` |
| `MEETING_ASSISTANT_WHISPER_MODEL` | `large-v3-turbo` |
| `MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE` | `ar` |
| `MEETING_ASSISTANT_SPEAKER_DIARIZATION` | `0` |

## Acceptance checklist

Run `.\accept_offline_bundle.ps1` after install, or verify manually:

- [ ] `install_from_usb.ps1` completes; `.active_profile` is `gpu` or `cpu`
- [ ] `accept_offline_bundle.ps1` exits 0
- [ ] `http://127.0.0.1:18080/v1/status` shows `model_ready: true`
- [ ] `MeetingAssistant.exe` opens; mic record + import work
- [ ] Transcription completes with no network
- [ ] Summary reaches Ollama on host
- [ ] Data persists in `{bundle}\data` and `{bundle}\meeting_outputs` after restart

## Build host client only

```powershell
.\packaging\offline\host-client\build_host_client.ps1
```

## Build inference images only

```powershell
docker build -f packaging/offline/images/Dockerfile.gpu -t meeting-assistant:gpu-bundle .
docker build -f packaging/offline/images/Dockerfile.cpu -t meeting-assistant:cpu-bundle .
```
