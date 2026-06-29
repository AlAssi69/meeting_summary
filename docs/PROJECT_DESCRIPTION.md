# Project description (for consultation)

## Name and purpose

**Local AI Meeting Assistant** is a **desktop app** for **privacy-oriented meeting workflows**: capture or import audio, **transcribe** it locally with **WhisperX** (ASR, forced alignment, and optional **speaker diarization** via pyannote), and **summarize** the transcript with a **local LLM** through **Ollama**—so **audio and text are not sent to cloud STT/LLM services** by design.

## Product goal

Give users a **single place** to: manage **sessions** (chat-style history), **record** or **upload** meeting audio, get a transcript (optionally **diarized** when that feature is enabled) and a **text summary** on disk, with **configurable prompts** so transcription and summarization match their domain (e.g. Arabic meetings, domain jargon).

## Current technical stack

| Layer | Technology |
|--------|------------|
| **UI** | **PySide6**, **Qt Quick (QML)** — responsive layout, light/dark themes |
| **Speech-to-text** | **WhisperX** (faster-whisper–compatible CT2 ASR, Wav2Vec2 alignment, optional **pyannote** diarization); models cached on disk; optional **CUDA**, automatic **CPU fallback** where configured |
| **LLM** | **Ollama** over HTTP (`/api/chat`; default host **`localhost` on Windows**, **`127.0.0.1` on Linux/macOS**, or override with `MEETING_ASSISTANT_OLLAMA_BASE_URL`) |
| **HTTP client** | **httpx** |
| **Model downloads** | **huggingface_hub** (Whisper CT2 snapshots and gated Hub models into a local cache) |
| **Persistence** | **SQLite** (sessions, messages, settings, `session_speakers`) when not in mock mode |
| **Background work** | **`QThread` workers** — **`TranscriptionWorker`** (transcribe + transcript file), **`SummarizeWorker`** (Ollama only), **`ModelDownloadWorker`** (model fetch) — so the GUI stays responsive |
| **Tests** | **pytest** (optional) |

**Optional system tool:** **FFmpeg** (see README for resolution order) for decoding and pre–ASR audio prep.

## Architecture (how it fits together)

- **Ports/adapters style:** Python separates **UI controllers**, **repositories** (SQLite vs in-memory), and **adapters** for WhisperX, Ollama, and mocks.
- **Pipeline:** **Prepare session artifact paths → Transcribe (WhisperX) → Write transcript → (optional) speaker-name intercept in UI → Summarize (Ollama) → Write summary.** Processing is **sequential** and **stateless for the LLM**: each summarization uses **only that run’s transcript** and **composed prompts**—**no cross-session memory**.
- **Artifacts:** Each session has a folder **`{meeting_output_root}/sessions/{artifacts_slug}/`** containing that session’s audio and `.txt` artifacts (transcript and summary). The app does not rely on legacy flat `recordings/`, `transcripts/`, and `summaries/` folders beside `sessions/` for new work (see README).
- **Mock mode** (`MEETING_ASSISTANT_MOCK`): fake delays, stub STT/LLM, in-memory sessions—used for UI/testing without full AI stack.

## Functional highlights

- **Sessions** with persistent history; **Arabic/English UI** chrome (RTL for Arabic), stored as `ui_language` (independent of Whisper’s transcription language).
- **Speaker diarization:** optional (default off). When enabled and pyannote runs successfully, transcript lines use **`SPEAKER_XX [MM:SS - MM:SS]:`**; the UI can collect display names, rewrite the transcript file, persist mappings in **`session_speakers`**, then run summarization. When disabled, lines use **`[MM:SS - MM:SS]:`** and summarization follows transcription directly.
- **Prompts:** global **LLM system** text and global **Whisper `initial_prompt`** bias, plus optional **per-recording** LLM and Whisper overrides on the message that carries audio.
- **Hugging Face token:** required when **speaker diarization** is enabled; stored in Settings (`hf_access_token`) with env fallbacks (see README).

## Important constraints and assumptions

- **Offline-first intent:** Whisper/inference uses **local files only** at load time; operators download models via the in-app UI or manual cache for **dev installs**. For **air-gapped USB delivery**, use the Path A bundle under [`packaging/offline/`](../packaging/offline/) (models baked into Docker images; host client sets `MEETING_ASSISTANT_WHISPER_API_URL`).
- **Ollama** must be **running locally** with a **pulled model** (configurable via env).
- **Pyannote** models are **gated** on the Hub; terms must be accepted and an **HF token** is required **when speaker diarization is enabled** (off by default).
- **Windows:** `main.py` prepends CUDA runtime DLL paths from the pinned **`nvidia-*`** wheels so GPU stacks can load reliably ([`nvidia_windows_dlls.py`](../src/meeting_assistant/nvidia_windows_dlls.py)).

## Documentation in the repo

- **[README.md](../README.md)** — setup, env vars, speech cache, quick start.
- **[OFFLINE_DOCKER_HANDOFF.md](OFFLINE_DOCKER_HANDOFF.md)** — air-gapped USB bundle (Path A: PyInstaller + headless WhisperX).
- **[packaging/offline/README.md](../packaging/offline/README.md)** — build scripts, compose files, operator runbook source (`RUNBOOK.txt` on USB).
- **[SRS.md](SRS.md)** — product/architecture requirements aligned with implementation.
- **[INSTALLATION_AR.md](INSTALLATION_AR.md)** — Arabic Windows installation and migration guide.
- **[Feature SRS - Speaker Diarization and Alignment.md](Feature%20SRS%20-%20Speaker%20Diarization%20and%20Alignment.md)** — addendum for diarization/alignment (implementation status at top).
- **[TROUBLESHOOTING_NLTK_PUNKT_TAB.md](TROUBLESHOOTING_NLTK_PUNKT_TAB.md)** — fixing the WhisperX `punkt_tab` (NLTK) alignment 500 error in the offline bundle.
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** — development setup, documentation sync rules, PR checklist.

## Likely consultation topics (context)

- **Scaling the AI stack** (GPU vs CPU, model sizes, download/cache strategy, diarization cost).
- **Quality tuning** (alignment language, jargon normalizer, prompt design for Arabic + English technical terms).
- **Packaging** — dev: PyInstaller host client + Docker inference images under `packaging/offline/`; see [OFFLINE_DOCKER_HANDOFF.md](OFFLINE_DOCKER_HANDOFF.md). Topics: shipping WhisperX + CUDA vs CPU-only, FFmpeg bundling, 64 GB+ USB images.
- **Arabic workflows** (UI vs transcription language, RTL, prompt design).

---

Point consultants at **[README.md](../README.md)** and **[SRS.md](SRS.md)** for full detail and environment defaults. For Arabic Windows setup, see **[INSTALLATION_AR.md](INSTALLATION_AR.md)**.
