# Local AI Meeting Assistant

A **desktop application** for **offline-capable** meeting workflows: record or upload audio, **transcribe** with **WhisperX** (ASR, forced alignment, and **speaker diarization** via pyannote), and **summarize** with a local LLM through **Ollama**—without sending audio or transcripts to the cloud by default.

The UI is **Qt Quick (QML)** on **PySide6**; Python owns persistence, AI adapters, and background work (`QThread` workers) so the interface stays responsive.

**More documentation**

- [docs/PROJECT_DESCRIPTION.md](docs/PROJECT_DESCRIPTION.md) — short consultation-ready overview (purpose, stack, constraints).
- [docs/SRS.md](docs/SRS.md) — Software Requirements Specification (intent and architecture).
- [docs/Feature SRS - Speaker Diarization and Alignment.md](docs/Feature%20SRS%20-%20Speaker%20Diarization%20and%20Alignment.md) — diarization and alignment addendum.

---

## Breaking changes

- **SQLite:** Deprecated **`app_settings`** keys (`global_default_prompt`, `prompt_bundle_v2_applied`) are **deleted on startup**. The legacy **`sessions.chat_prompt`** column is **dropped** when SQLite supports `DROP COLUMN` (3.35+). Older DB files missing newer message/session columns still get the usual **`ALTER TABLE … ADD COLUMN`** pass so the app can open them. Prefer a **fresh** `meetings.db` when you want a completely clean file; back up first if you need history.
- **`MEETING_ASSISTANT_TRANSCRIPTS`** is no longer supported. **New runs** write session audio and `.txt` artifacts (transcript and summary) under **`<meeting_output_root>/sessions/<artifacts_slug>/`** only. The types in `resolve_meeting_output_dirs` still expose logical `recordings/`, `transcripts/`, and `summaries/` under the output root (e.g. for tests and older helpers), but the GUI pipeline uses the per-session folder above—not a root-level `transcripts/` directory for those files.

---

## Project overview

| Area | What it does |
|------|----------------|
| **Sessions** | Chat-style sessions with local history (SQLite when not in mock mode). |
| **Audio** | Microphone capture (Qt Multimedia, when available) and file upload / drag-and-drop. |
| **Speech-to-text** | **WhisperX** (faster-whisper + alignment + pyannote diarization). A **Hugging Face access token** is **required** for the real WhisperX path: the engine refuses to transcribe without it (Hub-gated pyannote stack). Store the token in **Settings** (recommended) or set **`MEETING_ASSISTANT_HF_TOKEN`** (or `HF_TOKEN` / `HF_ACCESS_TOKEN` / `HUGGING_FACE_HUB_TOKEN`). Accept the **pyannote** model conditions on the Hub for that token. |
| **Summarization** | **Ollama** `/api/chat` with a configurable model and composed system prompt. |
| **Artifacts** | Per-session folder under `<output_root>/sessions/<name>/` (audio, transcript `.txt`, summary `.txt`). |
| **Prompts** | Separate **global Whisper context** (biases transcription) and **global LLM system** text (summarization), plus optional **per-recording** overrides stored with the session. |
| **Pipeline** | **`TranscriptionWorker`** then **`SummarizeWorker`** (after you confirm speaker names when diarization finds speakers). Stopping mid-run may leave a **partial transcript**; if summarization fails after a successful transcript, the app can still show transcript text with an **error placeholder** for the summary. |
| **UI language** | **Arabic** or **English** chrome (toolbar toggle); persisted as `ui_language` (`ar` / `en`). Default first-run UI language is **`ar`** ([`DEFAULT_UI_LANGUAGE`](src/meeting_assistant/core/constants.py)). Arabic uses **RTL** layout. Strings: [`src/meeting_assistant/i18n/ar_catalog.py`](src/meeting_assistant/i18n/ar_catalog.py); optional override [`src/meeting_assistant/translations/meeting_assistant_ar.qm`](src/meeting_assistant/translations/). Independent of `MEETING_ASSISTANT_WHISPER_LANGUAGE` (transcription language). |

**Speaker diarization** uses WhisperX and pyannote. Transcripts use lines like `SPEAKER_00 [MM:SS - MM:SS]: …`. After transcription, the chat can ask for **display names**; confirming **rewrites** the transcript `.txt` with those names and runs the summary. Mappings are stored in SQLite (`session_speakers`).

On **Windows**, `main.py` calls **`ensure_nvidia_pip_dll_directories()`** so CUDA runtime libraries shipped via the pinned **`nvidia-*`** wheels are discoverable when WhisperX uses the GPU.

---

## Models and services

| Piece | Technology | Notes |
|--------|------------|--------|
| **ASR** | WhisperX + **CTranslate2** (faster-whisper–compatible weights) | Default size key `large-v3` → Hub repo `Systran/faster-whisper-large-v3`. Other keys and custom `org/name` repos: see `FASTER_WHISPER_HF_REPOS` in [`src/meeting_assistant/config.py`](src/meeting_assistant/config.py). Inference uses **local files only** at load (`local_files_only=True`); download via UI or pre-populate cache under `MEETING_ASSISTANT_WHISPER_CACHE`. |
| **Alignment** | WhisperX `load_align_model` / `align` | Alignment language: `MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE` (default **`ar`** in code; set `auto` / `none` / empty to follow **ASR-detected** language). |
| **Diarization & speaker assignment** | WhisperX `DiarizationPipeline` + `assign_word_speakers` | pyannote stack behind WhisperX; **HF token required** for the current real pipeline. Exact checkpoint IDs depend on your installed **`whisperx`** version. |
| **Summarization** | **Ollama** `POST /api/chat` | Default model in code: `gemma4:e4b128k` (`MEETING_ASSISTANT_OLLAMA_MODEL`). |

---

## Dependencies

### Python

- **Python 3.11+** (matches [`pyproject.toml`](pyproject.toml) `requires-python`; 3.12 is a good default).
- Install runtime packages from the repo root:

```bash
pip install -r requirements.txt
```

| Package (from `requirements.txt`) | Role |
|-----------------------------------|------|
| **PySide6** | QML / Qt Quick desktop UI |
| **python-dotenv** | Optional load of repo-root `.env` (see [Configuration: `.env`](#configuration-env) ) |
| **whisperx** | ASR, alignment, diarization orchestration |
| **torch** | Backend for WhisperX (PyPI wheel is often **CPU-only**; see GPU note below) |
| **huggingface_hub** | Model download / cache |
| **httpx** | Ollama HTTP client |
| **nvidia-*** (pinned) | CUDA 12 runtime pieces on Windows for GPU stacks |

**Dev / lint (optional):** from repo root, `pip install '.[dev]'` then `ruff check src tests` (Ruff config in [`pyproject.toml`](pyproject.toml)).

**Tests:** `pytest` is not pinned in `requirements.txt`; `pip install pytest` to run the suite. Use **`PYTHONPATH`** pointing at **`src`** (see [Development](#development)).

### External tools

- **[Ollama](https://ollama.com/)** — local LLM server (`/api/chat`).
- **[FFmpeg](https://ffmpeg.org/)** — required for real transcription (decode + optional pre-ASR prep). Resolution: **`MEETING_ASSISTANT_FFMPEG_PATH`**, `ffmpeg` next to the app executable, then **`PATH`**. Example (Windows): `winget install ffmpeg`.
- **GPU (optional)** — CUDA improves WhisperX throughput; CPU fallback when acceleration fails. Install a **CUDA-enabled PyTorch** into the **same** venv if you need GPU (see below).

### PyTorch and CUDA

The **`torch`** line in `requirements.txt` is often **CPU-only**. WhisperX uses GPU only when **`torch.cuda.is_available()`** is true. For NVIDIA GPUs, reinstall PyTorch from [PyTorch Get Started](https://pytorch.org/get-started/locally/), for example:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

Verify:

```bash
python -c "import torch; print('cuda:', torch.cuda.is_available(), 'version:', torch.version.cuda)"
```

Pinned **`nvidia-*`** wheels do not replace a CUDA-capable **torch** wheel.

**Mock mode:** set `MEETING_ASSISTANT_MOCK=1` — FFmpeg is not required.

---

## Install

1. **Clone** the repository and enter the project directory (folder that contains `main.py`).

2. **Create a virtual environment**

```bash
python -m venv .venv
```

Activate:

- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source .venv/bin/activate`

3. **Install Python dependencies**

```bash
pip install -r requirements.txt
```

4. **Install FFmpeg** and **Ollama** on the host; pull your chosen Ollama model (must match or exceed what you set in `MEETING_ASSISTANT_OLLAMA_MODEL`).

5. **Optional:** copy [`.env.example`](.env.example) to **`.env`** in the repo root and set variables (never commit `.env`).

---

## Configuration: `.env`

At import time, [`src/meeting_assistant/config.py`](src/meeting_assistant/config.py) loads **`.env`** from the **repository root** (same folder as `main.py`) using **python-dotenv**, with **`override=False`**: variables already set in the OS environment **win** over `.env`.

If `python-dotenv` is missing, `.env` is skipped (the app still reads the real environment).

**Full variable reference:** tables below and the source in `config.py`. [`.env.example`](.env.example) lists common keys with comments.

---

## `src/meeting_assistant/core/constants.py` (summary)

These are stable identifiers and defaults used across the app (see the file for full strings).

| Symbol / group | Meaning |
|----------------|---------|
| **`MessageRole`**, **`MessageSystemKind`**, **`AssistantContentKind`** | Enums for persisted messages and assistant bubble kinds (`transcript`, `summary`, `speaker_map`, etc.). |
| **`AUDIO_EXTENSIONS`** | Allowed upload / drag-and-drop: `.mp3`, `.wav`, `.m4a`, `.webm`, `.ogg`, `.flac`. |
| **`SETTINGS_KEY_GLOBAL_LLM_SYSTEM`** | SQLite `app_settings` key for global LLM system prompt. |
| **`SETTINGS_KEY_GLOBAL_WHISPER_CONTEXT`** | Global Whisper `initial_prompt` bias text. |
| **`SETTINGS_KEY_MEETING_OUTPUT_ROOT`** | Optional custom meeting output root (unless overridden by `MEETING_ASSISTANT_OUTPUT_ROOT`). |
| **`SETTINGS_KEY_UI_LANGUAGE`** | `ui_language`: `ar` or `en`. |
| **`SETTINGS_KEY_HF_ACCESS_TOKEN`** | HF token stored in Settings (preferred over env when non-empty in resolvers). |
| **`SETTINGS_DEPRECATED_SQLITE_KEYS`** | Legacy keys stripped on startup if present. |
| **`DEFAULT_UI_LANGUAGE`** | First-run UI chrome default: **`ar`**. |
| **`DEFAULT_SUMMARY_PROMPT`** | Default Arabic structured summarization instructions (LLM system). |
| **`DEFAULT_WHISPER_CONTEXT`** | Default domain / glossary bias for Whisper. |
| **`DEFAULT_RECORDING_LLM_INSTRUCTIONS`** | Pre-filled per-recording LLM hint in the chat UI (user-editable). |
| **`DEFAULT_RECORDING_WHISPER_CONTEXT`** | Pre-filled per-recording Whisper context in the chat UI. |

---

## Configuration (environment variables)

All variables below are read in **`src/meeting_assistant/config.py`**. Defaults match the current codebase.

### Backend mode, debug, trace

| Variable | Default | Meaning |
|----------|---------|---------|
| `MEETING_ASSISTANT_MOCK` | `0` | If true: mock STT/LLM and in-memory sessions. If false: SQLite + WhisperX + Ollama. |
| `MEETING_ASSISTANT_DEBUG` | `0` | Extra debug UI where implemented (`DEBUG_UI`). |
| `MEETING_ASSISTANT_TRACE_LEVEL` | `0` | Terminal trace verbosity **0–3** (0 = default logging; 1 = main pipeline; 2 = sub-steps/I/O; 3 = fine-grained). If set, overrides `MEETING_ASSISTANT_VERBOSE`. |
| `MEETING_ASSISTANT_VERBOSE` | *(unset)* | Alias for the same **0–3** scale as `TRACE_LEVEL` when `TRACE_LEVEL` is unset. |

### Ollama

| Variable | Default | Meaning |
|----------|---------|---------|
| `MEETING_ASSISTANT_OLLAMA_BASE_URL` | *(unset)* | If non-empty, **full** base URL (e.g. `http://127.0.0.1:11434`). Overrides host/port. No trailing slash. |
| `MEETING_ASSISTANT_OLLAMA_HOST` | **`localhost`** on Windows; **`127.0.0.1`** on Linux/macOS | Host only. |
| `MEETING_ASSISTANT_OLLAMA_PORT` | `11434` | HTTP port. |
| `MEETING_ASSISTANT_OLLAMA_MODEL` | `gemma4:e4b128k` | Model name for `/api/chat`. |

If `MEETING_ASSISTANT_OLLAMA_BASE_URL` is unset, the client uses `http://{OLLAMA_HOST}:{OLLAMA_PORT}`.

### Hugging Face token (real transcription)

The process reads the **first non-empty** value among (after `.env` load):

`MEETING_ASSISTANT_HF_TOKEN`, `HF_ACCESS_TOKEN`, `HUGGING_FACE_HUB_TOKEN`, `HF_TOKEN`.

In-app **Settings** can override env when the stored token is non-empty (see `resolve_hf_access_token` in [`src/meeting_assistant/services/hf_token.py`](src/meeting_assistant/services/hf_token.py)).

### Whisper / WhisperX (ASR, alignment, device)

| Variable | Default | Meaning |
|----------|---------|---------|
| `MEETING_ASSISTANT_WHISPER_MODEL` | `large-v3` | Size key from `FASTER_WHISPER_HF_REPOS` or full Hub id `org/name` for custom CT2 snapshots. |
| `MEETING_ASSISTANT_WHISPER_CACHE` | `{PROJECT_ROOT}/models/whisper` | CT2 model cache (`download_root`). |
| `MEETING_ASSISTANT_PROJECT_ROOT` | Auto (two levels above `config.py`) | Repo root; affects default cache and default meeting output root. |
| `MEETING_ASSISTANT_WHISPER_LANGUAGE` | `auto` | Fixed ASR language (`ar`, `en`, …) or `auto` / `none` / empty for **automatic detection** (`WHISPER_LANGUAGE` = `None`). |
| `MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE` | **`ar`** | **Alignment-only** ISO code. Use `auto`, `none`, or empty to align using **ASR-detected** language instead of this default. |
| `MEETING_ASSISTANT_TRANSCRIPT_JARGON_NORMALIZE` | `0` | When `1`, optional **Ollama** post-pass on the transcript using composed Whisper context as glossary. |
| `MEETING_ASSISTANT_WHISPER_BEAM_SIZE` | `7` | Beam width; clamped **1–16** in code. |
| `MEETING_ASSISTANT_WHISPER_CONDITION_ON_PREVIOUS_TEXT` | `0` | If `1`, allow cross-window conditioning in faster-whisper (default off for fewer hallucinations). |
| `MEETING_ASSISTANT_WHISPER_NO_SPEECH_THRESHOLD` | `0.75` | Speech vs noise (0–1). |
| `MEETING_ASSISTANT_WHISPER_COMPRESSION_RATIO_THRESHOLD` | `2.4` | Repetition / compression ratio filter (1–10). |
| `MEETING_ASSISTANT_WHISPERX_DROP_SEGMENT_MIN_AVG_LOGPROB` | *(unset)* | Optional: drop ASR segments with avg logprob below this (unset = disabled). |
| `MEETING_ASSISTANT_WHISPERX_ASR_COMPRESSION_MIN_CHARS` | `24` | Minimum segment length for compression-ratio filtering (0–1000). |
| `MEETING_ASSISTANT_WHISPER_DEVICE` | `cuda` | `cpu`, `cuda`, or `auto`. |
| `MEETING_ASSISTANT_WHISPERX_BATCH_SIZE` | `8` | WhisperX transcribe batch size (1–64). Lower on low VRAM. |
| `MEETING_ASSISTANT_WHISPER_COMPUTE_TYPES` | *(built-in chain)* | Comma-separated CTranslate2 compute types to try in order (e.g. `float16,int8`). |
| `MEETING_ASSISTANT_WHISPER_MIN_BIN_BYTES` | *(per-model table)* | Override minimum `model.bin` size for cache completeness checks. |

### Data paths and outputs

| Variable | Default | Meaning |
|----------|---------|---------|
| `MEETING_ASSISTANT_DATA_DIR` | OS-specific (see below) | App data root; SQLite lives here unless `MEETING_ASSISTANT_DB` overrides. |
| `MEETING_ASSISTANT_DB` | `{DATA_DIR}/meetings.db` | SQLite path. |
| `MEETING_ASSISTANT_OUTPUT_ROOT` | *(unset)* | If set, **forces** meeting output root; GUI sessions use `sessions/` beneath it (overrides in-app custom folder). |

**Default `DATA_DIR`** when `MEETING_ASSISTANT_DATA_DIR` is unset (`_local_data_dir()` in `config.py`):

- **Windows:** `%LOCALAPPDATA%\MeetingAssistant` (when `LOCALAPPDATA` is set), else `~/.local/share/MeetingAssistant`.
- **Linux/macOS:** `$XDG_DATA_HOME/MeetingAssistant` when `XDG_DATA_HOME` is set; else **`~/.local/share/MeetingAssistant`**.

**Default meeting outputs** when neither env nor in-app override applies: **`{PROJECT_ROOT}/meeting_outputs`** with per-session folders under **`sessions/`**.

### Mock tuning

| Variable | Default | Meaning |
|----------|---------|---------|
| `MEETING_ASSISTANT_MOCK_DELAY` | `0.45` | Artificial delay (seconds) in mock transcription/summarization. |

### FFmpeg path and audio preprocessing

| Variable | Default | Meaning |
|----------|---------|---------|
| `MEETING_ASSISTANT_FFMPEG_PATH` | *(unset)* | Full path to `ffmpeg`; overrides lookup beside `sys.executable` and `PATH`. |
| `MEETING_ASSISTANT_AUDIO_PREP_ENABLED` | `1` | When `1`, FFmpeg sanitization to temp 16 kHz mono WAV before WhisperX. Set `0` to pass the original file through (when decode supports it). |
| `MEETING_ASSISTANT_AUDIO_PREP_KEEP_TEMP` | `0` | Keep temp prepped WAV files when `1` (debug). |
| `MEETING_ASSISTANT_AUDIO_PREP_FFMPEG_TIMEOUT_SEC` | `7200` | FFmpeg timeout (30–86400 seconds). |
| `MEETING_ASSISTANT_FFMPEG_AFILTER` | *(unset)* | Non-empty: full **`-af`** string (replaces structured high-pass + compressor + loudnorm chain). |
| `MEETING_ASSISTANT_AUDIO_PREP_HIGHPASS_HZ` | `80` | High-pass frequency (0–500). |
| `MEETING_ASSISTANT_AUDIO_PREP_ACOMP_THRESHOLD_DB` | `-18` | Compressor threshold dB (-80–0). |
| `MEETING_ASSISTANT_AUDIO_PREP_ACOMP_RATIO` | `3` | Compressor ratio (1–20). |
| `MEETING_ASSISTANT_AUDIO_PREP_ACOMP_ATTACK_MS` | `20` | Attack (0.1–2000 ms). |
| `MEETING_ASSISTANT_AUDIO_PREP_ACOMP_RELEASE_MS` | `250` | Release (1–5000 ms). |
| `MEETING_ASSISTANT_AUDIO_PREP_ACOMP_MAKEUP_DB` | `2` | Makeup gain (-12–24 dB). |
| `MEETING_ASSISTANT_AUDIO_PREP_LOUDNORM_ENABLED` | `1` | Append EBU `loudnorm` when `1` and no full `MEETING_ASSISTANT_FFMPEG_AFILTER` override. |
| `MEETING_ASSISTANT_AUDIO_PREP_LOUDNORM_I` | `-16` | Integrated loudness target (LUFS). |
| `MEETING_ASSISTANT_AUDIO_PREP_LOUDNORM_TP` | `-1.5` | True peak (dBTP). |
| `MEETING_ASSISTANT_AUDIO_PREP_LOUDNORM_LRA` | `11` | Loudness range target. |

Preprocessing logs use the logger **`meeting_assistant.audio_prep`** and the **`| AUDIO-PREP |`** prefix.

---

## Where configuration lives (layers)

| Layer | Location | What it controls |
|--------|-----------|------------------|
| **Environment / `.env`** | `config.py` | Feature flags, Ollama, Whisper, paths, mock timing, trace level. |
| **In-app settings** | SQLite via `SettingsController` | Global LLM system text, global Whisper context, optional meeting output root, HF token (`SETTINGS_KEY_HF_ACCESS_TOKEN`). `MEETING_ASSISTANT_OUTPUT_ROOT` still wins over the custom folder. |
| **UI locale** | SQLite `app_settings` (`ui_language`) | `ar` / `en`; `LocaleController`. |
| **Per-session / per-recording prompts** | Message/session rows | Optional recording-level Whisper + LLM instructions; composed at pipeline time. |
| **Constants** | [`src/meeting_assistant/core/constants.py`](src/meeting_assistant/core/constants.py) | Extensions, settings keys, default prompts, enums. |
| **Output layout** | [`src/meeting_assistant/services/output_paths.py`](src/meeting_assistant/services/output_paths.py) | Resolution of meeting file paths vs env overrides. |

---

## How to run

From the repository root (directory containing **`main.py`**):

```bash
python main.py
```

`main.py` adds `src` to `sys.path` and loads QML from `src/meeting_assistant/qml/`.

**Checklist (real backend, default):**

1. **Ollama** running with the model you configure (`MEETING_ASSISTANT_OLLAMA_MODEL`, default `gemma4:e4b128k`).
2. **Hugging Face token** set (Settings or env); pyannote terms accepted on the Hub.
3. **Whisper CT2** snapshot complete under `MEETING_ASSISTANT_WHISPER_CACHE` (in-app download when using the real backend).
4. **FFmpeg** discoverable (see above).

**Mock mode (no AI stack):**

```powershell
$env:MEETING_ASSISTANT_MOCK="1"
python main.py
```

---

## How to use (typical flow)

1. **Create or open a session** in the sidebar.
2. **Record** audio or **upload** / drag-and-drop a supported file (see `AUDIO_EXTENSIONS` in `constants.py`).
3. **Optional:** edit global prompts in **Settings**, or per-recording Whisper / LLM hints on the message before send.
4. **Process:** the app runs **transcription** (WhisperX: ASR → align → diarize when token is valid), writes a **transcript `.txt`**, and may prompt for **speaker display names**; after confirm, it runs **summarization** via Ollama and writes a **summary `.txt`**.
5. **Artifacts** live under `{meeting_output_root}/sessions/{artifacts_slug}/` (default root: `meeting_outputs` under the project).

**Summarize-only:** from an existing transcript, only Ollama summarization runs (no new ASR).

There is **no cross-session LLM memory**: each summary uses only that run’s transcript and composed prompts.

---

## Current pipeline (detail)

1. **Prepare** — Resolve session output folder under `sessions/`, build prompt snapshot (global + per-recording).
2. **Transcribe** — WhisperX with `initial_prompt` from composed Whisper context. Optional **`MEETING_ASSISTANT_TRANSCRIPT_JARGON_NORMALIZE=1`**: extra Ollama pass using the same glossary text.
3. **Persist transcript** — `.txt` with `SPEAKER_XX` lines when applicable; speaker **Confirm** rewrites file and SQLite `session_speakers`.
4. **Summarize** — Ollama: **system** = composed LLM prompt; **user** = transcript only.
5. **Persist summary** — `.txt` + chat bubble.

**Mock mode:** artificial delays; in-memory sessions; no real Whisper/Ollama/SQLite persistence paths for AI.

---

## Prompt composition

Merged in [`src/meeting_assistant/services/prompt_composition.py`](src/meeting_assistant/services/prompt_composition.py); accessors in [`src/meeting_assistant/services/prompts.py`](src/meeting_assistant/services/prompts.py).

- **Whisper `initial_prompt`** — Global Whisper context + per-recording Whisper context (suffix preserved if over ~1800 characters).
- **LLM system** — Global LLM system + per-recording summarization instructions.
- **LLM user** — Transcript text only.

### Arabic meetings with English technical terms

1. Put a **mixed glossary** in global and/or per-recording **Whisper** context (Arabic plus exact Latin spellings).
2. Prefer **`MEETING_ASSISTANT_WHISPER_LANGUAGE=auto`** for code-switching when appropriate.
3. If alignment drifts under auto ASR, set **`MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE=ar`** explicitly (this is already the **code default**; use `auto` to follow detection).
4. Optional **`MEETING_ASSISTANT_TRANSCRIPT_JARGON_NORMALIZE=1`** for an Ollama “technical editor” pass.

---

## In-app settings (persisted)

When not in mock mode: global LLM system prompt, global Whisper context, optional meeting files folder, HF token, UI language — stored in SQLite (`app_settings` keys from `constants.py`). Edited via **`app.settingsController`** and **`app.localeController`** in QML.

---

## UI language, RTL, and translations

- Toolbar toggle **English** ↔ **العربية**; persisted as `ui_language`.
- **Default** first run: **Arabic** (`DEFAULT_UI_LANGUAGE`).
- **RTL** for Arabic; mirrored chat alignment as implemented.
- **Catalog:** [`src/meeting_assistant/i18n/ar_catalog.py`](src/meeting_assistant/i18n/ar_catalog.py).
- **Optional `.qm`:** `meeting_assistant_ar.qm` under `src/meeting_assistant/translations/` loads after the catalog.

---

## Architecture (high level)

- **UI:** QML [`src/meeting_assistant/qml/Main.qml`](src/meeting_assistant/qml/Main.qml) → context property **`app`** (`AppFacade`).
- **Ports:** [`src/meeting_assistant/ports/`](src/meeting_assistant/ports/) — session, transcription, summarization contracts.
- **Adapters:** [`src/meeting_assistant/adapters/`](src/meeting_assistant/adapters/) — SQLite, WhisperX, Ollama, mocks. Wiring: **`app_context.build_app_facade()`** from **`config.USE_MOCK_BACKEND`**.
- **Workers:** [`src/meeting_assistant/workers/`](src/meeting_assistant/workers/) — `TranscriptionWorker`, `SummarizeWorker`, `ModelDownloadWorker`.
- **Composition:** [`src/meeting_assistant/app_context.py`](src/meeting_assistant/app_context.py) builds the facade after `QQmlApplicationEngine` so translators install before/during QML load.

---

## Project structure

```text
meeting_summary/
├── main.py                          # Entry: DLL paths (Windows), logging, QML, context property `app`
├── requirements.txt                 # Runtime pip dependencies
├── pyproject.toml                   # Ruff, requires-python, optional dev extras
├── LICENSE                          # Apache License 2.0
├── .env.example                     # Example environment (copy to .env; do not commit secrets)
├── docs/
│   ├── SRS.md
│   ├── PROJECT_DESCRIPTION.md
│   └── Feature SRS - Speaker Diarization and Alignment.md
├── README.md
├── scripts/
│   ├── audit_sqlite_privacy.py
│   └── audit_repo_before_github.py
├── tests/                           # pytest (set PYTHONPATH=src)
│   ├── conftest.py
│   ├── test_prompt_composition.py
│   ├── test_output_paths.py
│   ├── test_history_and_summarize.py
│   ├── test_processing_stop.py
│   ├── test_chat_controller_guards.py
│   ├── test_chat_controller_speaker_map_session_switch.py
│   ├── test_ui_language_setting.py
│   ├── test_sqlite_hf_and_speakers.py
│   ├── test_speaker_mapping.py
│   ├── test_diarization_format.py
│   ├── test_transcript_jargon_normalizer.py
│   ├── test_whisperx_asr_segment_filter.py
│   ├── test_trace_logging.py
│   ├── test_ffmpeg_audio_preprocess.py
│   └── test_compute_type_candidates.py
└── src/
    └── meeting_assistant/
        ├── config.py                # Environment configuration (single source for env vars)
        ├── app_context.py
        ├── logging_setup.py
        ├── nvidia_windows_dlls.py
        ├── core/                    # models.py, constants.py, enums
        ├── ports/
        ├── adapters/
        ├── services/                # whisperx_engine, output_paths, prompts, ffmpeg_audio_preprocess, …
        ├── workers/
        ├── ui/
        ├── i18n/
        ├── translations/
        └── qml/
```

---

## Development

```powershell
# Windows PowerShell
$env:PYTHONPATH = "$PWD\src"
pytest
```

```bash
# macOS / Linux
PYTHONPATH=src pytest
```

Optional: `pip install '.[dev]'` then `ruff check src tests`.

---

## Troubleshooting

- **QML on Windows:** `main.py` sets `QT_QUICK_CONTROLS_STYLE=Basic` for consistent styling.
- **Ollama:** Use `MEETING_ASSISTANT_OLLAMA_BASE_URL` or adjust host/port defaults (Windows **`localhost`**, Linux/macOS **`127.0.0.1`**).
- **Whisper cache incomplete:** Fill `MEETING_ASSISTANT_WHISPER_CACHE` or use in-app download; check `MEETING_ASSISTANT_WHISPER_MIN_BIN_BYTES` for custom repos.
- **GPU errors:** Try `MEETING_ASSISTANT_WHISPER_DEVICE=cpu` or tune `MEETING_ASSISTANT_WHISPER_COMPUTE_TYPES`; Windows CUDA DLLs: `nvidia-*` wheels + `nvidia_windows_dlls.py`.
- **TorchCodec / pyannote warning on Windows:** Pip TorchCodec may lack native DLLs; WhisperX still decodes via FFmpeg when FFmpeg resolves. Benign warning filtered at startup in `main.py`.
- **HF token:** Real transcription **requires** a non-empty token (Settings or env); accept Hub model terms.
- **pytest import errors:** Set `PYTHONPATH` to **`src`**.

---

## License

This project is licensed under the **Apache License 2.0** — see [LICENSE](LICENSE).

---

## Contributing

Issues and pull requests are welcome. When changing behavior, update **`config.py`**, **`docs/SRS.md`**, **`docs/PROJECT_DESCRIPTION.md`** (if the high-level story changes), and this README so they stay aligned.
