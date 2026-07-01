# Fixing the WhisperX `punkt_tab` Transcription Error

The pipeline order is: load model → **ASR transcribe** (this is the compute spike) → **alignment** (fails here) → diarization (optional). That's why usage spikes then drops.

## Option A — Hotfix the running container (target HAS internet)

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

## Option B — Hotfix an AIR-GAPPED target (no internet)

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

**Verify with the same `curl.exe` POST as Option A. Same reinstall caveat applies.**

---


## Verification checklist

- [ ] `docker exec meeting-assistant-whisper python -c "import nltk; nltk.data.find('tokenizers/punkt_tab/english'); print('OK')"` prints `OK`
- [ ] `curl.exe -sS -X POST -F "audio=@<file>" http://127.0.0.1:18080/v1/transcribe` returns JSON with a non-empty `"text"`
- [ ] The desktop app transcribes without the `500` error
