# Project description (for consultation)

## Name and purpose

**Local AI Meeting Assistant** is a **desktop app** for **privacy-oriented meeting workflows**: capture or import audio, **transcribe** it locally with **WhisperX** (ASR, forced alignment, and **speaker diarization** via pyannote), and **summarize** the transcript with a **local LLM** through **Ollama**—so **audio and text are not sent to cloud STT/LLM services** by design.

## Product goal

Give users a **single place** to: manage **sessions** (chat-style history), **record** or **upload** meeting audio, get a **diarized transcript** (when speakers are detected) and a **text summary** on disk, with **configurable prompts** so transcription and summarization match their domain (e.g. Arabic meetings, domain jargon).

## Current technical stack

| Layer | Technology |
|--------|------------|
| **UI** | **PySide6**, **Qt Quick (QML)** — responsive layout, light/dark themes |
| **Speech-to-text** | **WhisperX** (faster-whisper–compatible CT2 ASR, Wav2Vec2 alignment, **pyannote** diarization); models cached on disk; optional **CUDA**, automatic **CPU fallback** where configured |
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
- **Speaker diarization:** when pyannote runs successfully, transcript lines use **`SPEAKER_XX [MM:SS - MM:SS]:`**; the UI can collect display names, rewrite the transcript file, persist mappings in **`session_speakers`**, then run summarization.
- **Prompts:** global **LLM system** text and global **Whisper `initial_prompt`** bias, plus optional **per-recording** LLM and Whisper overrides on the message that carries audio.
- **Hugging Face token:** required for the **real** WhisperX transcription path (diarization is part of that pipeline); stored in Settings (`hf_access_token`) with env fallbacks (see README).

## Important constraints and assumptions

- **Offline-first intent:** Whisper/inference uses **local files only** at load time; operators are expected to **download** models when needed (UI or manual cache).
- **Ollama** must be **running locally** with a **pulled model** (configurable via env).
- **Pyannote** models are **gated** on the Hub; terms must be accepted and the same **HF token** requirement as above applies for real transcription.
- **Windows:** `main.py` prepends CUDA runtime DLL paths from the pinned **`nvidia-*`** wheels so GPU stacks can load reliably ([`nvidia_windows_dlls.py`](../src/meeting_assistant/nvidia_windows_dlls.py)).

## Documentation in the repo

- **[README.md](../README.md)** — setup, env vars, speech cache, quick start.
- **[SRS.md](SRS.md)** — product/architecture requirements aligned with implementation.
- **[Feature SRS - Speaker Diarization and Alignment.md](Feature SRS - Speaker Diarization and Alignment.md)** — addendum for diarization/alignment (implementation status at top).

## Likely consultation topics (context)

- **Scaling the AI stack** (GPU vs CPU, model sizes, download/cache strategy, diarization cost).
- **Quality tuning** (alignment language, jargon normalizer, prompt design for Arabic + English technical terms).
- **Packaging** (PyInstaller/briefcase, shipping WhisperX + CUDA vs CPU-only, FFmpeg bundling).
- **Arabic workflows** (UI vs transcription language, RTL, prompt design).

---

Point consultants at **[README.md](../README.md)** and **[SRS.md](SRS.md)** for full detail and environment defaults.
