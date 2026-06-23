# Software Requirements Specification (SRS)

## Project: Local AI Meeting Assistant (QML / Python)

**Operational reference:** For environment variables, defaults, and runbooks, see [README.md](../README.md). This SRS states product intent and architecture; the README stays aligned with `src/meeting_assistant/config.py` and deployment details.

**Related docs:** [PROJECT_DESCRIPTION.md](PROJECT_DESCRIPTION.md) · [INSTALLATION_AR.md](INSTALLATION_AR.md) · [Feature SRS - Speaker Diarization and Alignment.md](Feature%20SRS%20-%20Speaker%20Diarization%20and%20Alignment.md)

---

### 1. Introduction

**1.1 Purpose**

This document defines the architecture and requirements for a minimal desktop application that supports offline-capable meeting workflows: record or upload audio, transcribe with a local **WhisperX** pipeline (ASR, forced alignment, **pyannote-backed diarization** bundled in the same path), and summarize with a local LLM through **Ollama**, without sending audio or transcripts to the cloud. In the **non-mock** configuration, the WhisperX transcription engine **requires** a valid **Hugging Face access token** (Settings or environment) because diarization is integrated into the shipped pipeline and the engine refuses to run without it; see [README.md](../README.md).

**1.2 Scope**

The software runs processing locally to protect data privacy. The UI uses a sidebar for sessions and a primary chat-style surface. The AI pipeline is sequential (**Audio → Transcript → Summary**) and **stateless across turns**: each summarization run uses only the current transcript and the prompts resolved for that run (no cross-session LLM memory).

**1.3 Development and testing**

A **mock backend** (environment-controlled) may substitute stub transcription, summarization, and in-memory sessions so the UI and wiring can be exercised without Whisper, Ollama, or SQLite. See [README.md](../README.md) (`MEETING_ASSISTANT_MOCK`).

---

### 2. System Architecture

**2.1 Frontend**

* **Framework:** **PySide6** with **Qt Quick (QML)**. The shipped product targets PySide6 only (not PyQt6).
* **Design:** Hardware-accelerated, responsive layout; light/dark theming.
* **Locale:** The interface supports **Arabic** and **English** UI chrome. The user can switch language from the toolbar; the choice is persisted in **`app_settings`** as **`ui_language`** (`ar` or `en`; default **`ar`**). Arabic uses **RTL** layout and mirrored chat alignment where applicable. Runtime Arabic strings are driven by **`src/meeting_assistant/i18n/ar_catalog.py`** (optional compiled **`meeting_assistant_ar.qm`** in **`src/meeting_assistant/translations/`** may override). UI language is **independent** of **`MEETING_ASSISTANT_WHISPER_LANGUAGE`** (speech decoding language).

**2.2 Backend**

* **Language:** Python **3.11+** (3.12 recommended; see `pyproject.toml` `requires-python`).
* **Responsibilities:** Persistence, AI adapters, file paths, prompt composition, and background work on **worker threads** (`QThread`) so the GUI thread stays responsive.

**2.3 AI pipeline**

* **STT:** **WhisperX** (CTranslate2 ASR via faster-whisper-compatible weights, forced alignment, pyannote diarization and speaker assignment in the default real path). Models are loaded with **local files only** at inference (no implicit Hub download). Operators must supply a **Hugging Face token** accepted for the gated pyannote models used by the installed **whisperx** version. Model cache and download behavior are described in the README.
* **LLM:** **Ollama** HTTP API (`/api/chat`).
* **Ollama addressing:** Default host is **`localhost` on Windows** and **`127.0.0.1` on Linux/macOS** (see `config.py`; Windows default targets typical WSL2 port-forwarding). Port is configurable; default **11434**. Override with **`MEETING_ASSISTANT_OLLAMA_HOST`** / **`MEETING_ASSISTANT_OLLAMA_PORT`**, or set **`MEETING_ASSISTANT_OLLAMA_BASE_URL`** to a full base URL (overrides host/port). Details are documented in the README.

**2.4 Data storage (SQLite)**

* **Database:** Single SQLite file (e.g. under the configured app data directory unless overridden).
* **`sessions`:** `id` (primary key), `title`, `created_at`, **`artifacts_slug`** (unique folder name under the meeting output tree).
* **`messages`:** `id`, `session_id`, `role` (e.g. user / assistant / system), `content`, `file_path`, `created_at`, `system_kind` (for system banner severity), **`recording_llm_instructions`** and **`recording_whisper_context`** (optional per-recording prompt layers; see §3.3), **`assistant_kind`** (e.g. transcript vs summary for assistant bubbles).
* **`app_settings`:** Key/value rows for global LLM system text (`global_llm_system_prompt`), global Whisper transcription context (`global_whisper_context`), optional meeting output root (`meeting_output_root`), **`ui_language`** (`ar` / `en`), Hugging Face token (`hf_access_token`) for the real WhisperX path, and related keys documented in the README. Deprecated keys (`global_default_prompt`, `prompt_bundle_v2_applied`) are deleted on startup.
* **`session_speakers`:** `id` (INTEGER PRIMARY KEY AUTOINCREMENT), `session_id` (TEXT, FOREIGN KEY to `sessions(id)` ON DELETE CASCADE), `speaker_key` (TEXT, e.g. `SPEAKER_00`), `speaker_name` (TEXT, user display name), UNIQUE(`session_id`, `speaker_key`). See [Feature SRS - Speaker Diarization and Alignment.md](Feature%20SRS%20-%20Speaker%20Diarization%20and%20Alignment.md).

---

### 3. Functional Requirements

**3.1 Session management (sidebar)**

* Create, switch, and persist sessions; list history ordered by recency.
* When the mock backend is off, persistence uses SQLite; mock mode uses an in-memory store.

**3.2 Input handling (chat area)**

* **Supported audio for upload and drag-and-drop:** `.mp3`, `.wav`, `.m4a`, `.webm`, `.ogg`, `.flac` (see `AUDIO_EXTENSIONS` in `src/meeting_assistant/core/constants.py`).
* **Recording:** A record control captures microphone audio via Qt Multimedia when available. While recording, audio is written to a **unique temporary filename under that session’s artifact directory** — i.e. **`{meeting_output_root}/sessions/{artifacts_slug}/`** once the session has a slug (see README for output root resolution), not necessarily the OS temp directory. After stop, that file is passed to the STT pipeline like an uploaded file.

**3.3 Prompt management**

* **Global settings (persisted in SQLite when not in mock mode):**
  * **Global LLM system text** — default summarization behavior (system role to Ollama).
  * **Global Whisper context** — optional text passed as Whisper `initial_prompt` to bias transcription.
  * **Optional meeting files folder** — overrides default output root unless superseded by environment (see README).
* **Per-recording overrides:** For each **user message that carries an audio file**, the user may supply optional **recording-specific LLM instructions** and **recording-specific Whisper context**. These are stored on that message row and composed at pipeline time with the global strings (see `src/meeting_assistant/services/prompt_composition.py`). The LLM **user** message for summarization is **transcript text only**; instructions live in the system role.
* **Breaking upgrades:** Deprecated **`app_settings`** keys (`global_default_prompt`, `prompt_bundle_v2_applied`) and the legacy **`sessions.chat_prompt`** column are removed on startup (see README *Breaking changes*). A **fresh SQLite file** is still recommended if the on-disk layout predates tables this app expects.

**3.4 User interface language**

* The application shall provide a **language toggle** between **Arabic** and **English** for all UI chrome (labels, dialogs, status messages).
* The selected language shall be **persisted** (SQLite when not in mock mode; in-memory settings when mock mode is on).
* **Arabic** shall use **RTL** layout at the application level; **English** shall use **LTR**.
* UI language requirements shall **not** imply automatic translation of user-authored content (transcripts, summaries, or stored prompt fields); default summarization and Whisper prompt strings in configuration remain separate from chrome localization.

**3.5 AI processing pipeline execution**

* **Phase 1 — Transcription:** On audio input, run **WhisperX** with composed `initial_prompt`; show a transcribing state; show transcript in chat; write a `.txt` transcript under the configured output tree; allow opening the file from the UI where implemented. When the optional **`MEETING_ASSISTANT_TRANSCRIPT_JARGON_NORMALIZE`** flag is enabled (see README), the application may insert an additional **Ollama** pass after ASR to normalize obvious Arabized English technical terms using the same composed Whisper context as a glossary; the persisted transcript reflects successful normalization. **`TranscriptionWorker`** emits **`finished_raw(transcript, txt_path, speaker_keys)`** and does not run summarization.
* **Speaker mapping (intercept):** When one or more speaker keys are present, the pipeline **halts** after Phase 1. The UI collects optional `SPEAKER_XX` → display name mappings; on confirm, the transcript file and **`session_speakers`** rows are updated (see Feature SRS). When there are no speaker keys, summarization starts immediately.
* **Phase 2 — Summarization:** **`SummarizeWorker`** sends Ollama a **system** message built from global + per-recording LLM instructions and a **user** message that is the transcript only; show a generating state; persist summary `.txt` and show the summary in chat.
* **Re-run summary:** From an existing transcript, summarization may run without re-transcription (see README).

---

### 4. Non-Functional Requirements

**4.1 Privacy**

Local processing only: no cloud APIs for STT/LLM in the default configuration. Ollama and Whisper are expected to run on the same machine as the app.

**4.2 UI responsiveness**

Heavy work (Whisper load/transcribe, Ollama HTTP) must not block the QML GUI thread; use dedicated workers (`QThread`).

**4.3 Scalability and performance**

* SQLite should remain suitable for large numbers of sessions without complex operations for normal UI use.
* **Whisper acceleration:** The default configuration prefers **CUDA** when requested (`MEETING_ASSISTANT_WHISPER_DEVICE`, default `cuda`), with **CPU fallback** when the accelerator is unavailable or fails. An **`auto`** device mode and explicit **`cpu`** are supported. This is **not** the same as “silent auto-detect only”: operators choose device policy via configuration (see README). Compute type fallbacks (e.g. float16 → int8) are documented there.

---

### 5. Traceability

When behavior changes, update this SRS for intent and [README.md](../README.md) for exact defaults, env vars, and file layout so they stay consistent with `src/meeting_assistant/`. See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full sync matrix and PR checklist.
