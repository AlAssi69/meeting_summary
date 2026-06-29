# Fixing the WhisperX `punkt_tab` Transcription Error

This guide explains the `500 Internal Server Error` that occurs during transcription in
the offline bundle, its root cause, and **four** approaches to fix it — ordered from
fastest hotfix to permanent fix.

---

## 1. Symptoms

- In the desktop app, transcription fails with:

  ```
  Server error '500 Internal Server Error' for url 'http://127.0.0.1:18080/v1/transcribe'
  ```

- In Docker, **GPU/CPU usage ramps up, then drops to zero** right when the error appears
  (the ASR transcription runs, then alignment immediately fails).

- Calling the endpoint directly returns a JSON body containing:

  ```
  Resource 'punkt_tab' not found. Please use the NLTK Downloader to obtain the resource ...
  Attempted to load 'tokenizers/punkt_tab/english/'
  Searched in: /root/nltk_data, /opt/venv/nltk_data, /opt/venv/share/nltk_data, ...
  ```

---

## 2. Root cause

The desktop app POSTs audio to the headless WhisperX container at
`http://127.0.0.1:18080/v1/transcribe`. The HTTP `500` is a **generic wrapper** — the real
error is in the JSON body and the container logs.

WhisperX's **forced-alignment** step uses an NLTK sentence tokenizer
(`tokenizers/punkt_tab/<lang>.pickle`). This NLTK data is fetched **lazily at `align()`
time**, not by `whisperx.load_align_model()`. The image build only ran
`load_align_model()` (which downloads the wav2vec2 alignment weights), so `punkt_tab` was
**never baked into the offline image**.

At runtime the container runs with `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` (and often
no internet), so NLTK cannot download `punkt_tab` on demand →
`LookupError: Resource 'punkt_tab' not found` → HTTP 500.

> The pipeline order is: load model → **ASR transcribe** (this is the compute spike) →
> **alignment** (fails here) → diarization (optional). That's why usage spikes then drops.

---

## 3. Diagnosis commands

Run these on the target machine to confirm the cause:

```powershell
# Real traceback (look for the line after "Transcription failed")
docker logs --tail 200 meeting-assistant-whisper

# Engine/model state — last_failure_kind will be "" (not a GPU or HF-auth failure)
curl.exe http://127.0.0.1:18080/v1/status

# Reproduce and see the actual JSON error body instead of the generic 500
curl.exe -sS -m 600 -X POST -F "audio=@F:\Test_1.mp3" http://127.0.0.1:18080/v1/transcribe
```

> **PowerShell note:** the bare word `curl` is an alias for `Invoke-WebRequest`, which does
> **not** accept curl flags like `-X` or `-F`. Always use `curl.exe` explicitly on Windows.

---

## 4. Prep: identify the active image tag

Several options need the image tag backing the running container
(`meeting-assistant:cpu-bundle` or `meeting-assistant:gpu-bundle`):

```powershell
docker inspect meeting-assistant-whisper --format "{{.Config.Image}}"
```

The value is referred to as `<IMAGE_TAG>` below.

---

## 5. Option A — Hotfix the running container (target HAS internet)

**Fastest.** Use when the machine can reach the internet and you need it working now.

```powershell
# 1. Download the missing NLTK tokenizers into the running container
docker exec meeting-assistant-whisper python -c "import nltk; nltk.download('punkt_tab'); nltk.download('punkt')"

# 2. Verify the resource now loads (should print: punkt_tab OK)
docker exec meeting-assistant-whisper python -c "import nltk; nltk.data.find('tokenizers/punkt_tab/english'); print('punkt_tab OK')"

# 3. Persist it into the image so it survives container restart/recreate
docker commit meeting-assistant-whisper <IMAGE_TAG>
```

**Verify end-to-end:**

```powershell
curl.exe -sS -m 600 -X POST -F "audio=@F:\Test_1.mp3" http://127.0.0.1:18080/v1/transcribe
```

You should now get a JSON body with a populated `"text"` field.

> The `docker exec` step fixes it immediately, but the data lives only in the container's
> writable layer — a `docker compose down`/recreate loses it. `docker commit` bakes it into
> the image. **Caveat:** re-running `install_from_usb.ps1` reloads the original tar and
> overwrites the commit, so this is an *until-next-reinstall* fix. For durability use Option D.

---

## 6. Option B — Hotfix an AIR-GAPPED target (no internet)

Fetch the data on an internet-connected machine, carry it over (USB), and inject it.

**On a machine WITH internet + Python:**

```powershell
python -c "import nltk; nltk.download('punkt_tab', download_dir='nltk_data'); nltk.download('punkt', download_dir='nltk_data')"
```

This creates an `nltk_data` folder. Copy it to the target via USB. **On the target:**

```powershell
# Copy the data into the container's NLTK search path
docker cp nltk_data meeting-assistant-whisper:/root/nltk_data

# Verify it loads
docker exec meeting-assistant-whisper python -c "import nltk; nltk.data.find('tokenizers/punkt_tab/english'); print('punkt_tab OK')"

# Persist into the image
docker commit meeting-assistant-whisper <IMAGE_TAG>
```

Verify with the same `curl.exe` POST as Option A. Same reinstall caveat applies.

---

## 7. Option C — Persistent volume (survives recreate without `docker commit`)

Use if you prefer not to `docker commit` and want clean persistence across recreation.

1. In `packaging/offline/compose/compose.yml`, under the `whisper` service, add an
   `NLTK_DATA` env and a named volume:

   ```yaml
     whisper:
       environment:
         NLTK_DATA: /opt/nltk_data
       volumes:
         - meeting_assistant_nltk:/opt/nltk_data
   # ... and at the bottom of the file:
   volumes:
     meeting_assistant_ollama:
     meeting_assistant_nltk:
   ```

2. Recreate the stack and populate the volume (internet path shown; for air-gapped, use
   `docker cp` into `/opt/nltk_data`):

   ```powershell
   docker compose -f compose.yml up -d
   docker exec meeting-assistant-whisper python -c "import nltk; nltk.download('punkt_tab', download_dir='/opt/nltk_data'); nltk.download('punkt', download_dir='/opt/nltk_data')"
   ```

> More involved and changes the deployment topology — pick only if you specifically want a
> volume-based approach.

---

## 8. Option D — Permanent rebuild & redeploy (RECOMMENDED)

Bakes the tokenizers into every future image. The code changes are **already in the repo**:

- `packaging/offline/scripts/preload_models.py` → `seed_nltk_punkt()` downloads
  `punkt_tab`/`punkt` at build time (called from the `align` stage).
- `packaging/offline/images/Dockerfile.cpu` and `Dockerfile.gpu` →
  `NLTK_DATA=/opt/meeting-assistant/models/nltk` (stable baked-in path).

**On the build machine (Docker + internet):**

```powershell
# 0. (recommended) Set an HF token so model preloads don't hit Hub rate limits
$env:HF_TOKEN = "hf_xxxxxxxx"

# 1. Rebuild images + regenerate the USB bundle (images, tars, scripts, host client)
.\packaging\offline\scripts\build_usb_bundle.ps1
```

To rebuild just one image for a quick test (without the full bundle):

```powershell
$env:DOCKER_BUILDKIT = "1"
docker build -f packaging/offline/images/Dockerfile.cpu `
  --build-arg PRELOAD_MODELS=1 `
  --build-arg WHISPER_MODEL=large-v3-turbo `
  --build-arg WHISPER_ALIGN_LANGUAGE=ar `
  --build-arg HF_TOKEN=$env:HF_TOKEN `
  -t meeting-assistant:cpu-bundle .
```

**Deploy to the target:**

```powershell
# Copy the whole usb-bundle folder to USB → target, then on the target:
.\install_from_usb.ps1
.\accept_offline_bundle.ps1 -TestAudioPath "F:\Test_1.mp3"   # smoke test includes a transcribe
.\launch_host_client.ps1
```

The `accept_offline_bundle.ps1 -TestAudioPath ...` step exercises transcription and confirms
the fix in one shot.

---

## 9. Which option should I choose?

| Situation | Option |
|---|---|
| Need it working now, target **has internet** | **A** |
| Need it working now, target is **air-gapped** | **B** |
| Want it fixed for **all future installs** | **D** (do this regardless) |
| Prefer a **volume** over `docker commit` | **C** |

**Recommendation:** run **Option A** (or **B**) now to unblock the machine, then do
**Option D** so the next USB build ships correctly and the error never recurs.

---

## 10. Verification checklist

- [ ] `docker exec meeting-assistant-whisper python -c "import nltk; nltk.data.find('tokenizers/punkt_tab/english'); print('OK')"` prints `OK`
- [ ] `curl.exe -sS -X POST -F "audio=@<file>" http://127.0.0.1:18080/v1/transcribe` returns JSON with a non-empty `"text"`
- [ ] The desktop app transcribes without the `500` error
- [ ] (Option D) A fresh `install_from_usb.ps1` + `accept_offline_bundle.ps1 -TestAudioPath` passes
