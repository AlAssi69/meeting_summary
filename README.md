# 🗂️ Local AI Meeting Assistant

A **desktop application** 💻 for **offline-capable** meeting workflows: record or upload audio, **transcribe** with **WhisperX** 🎙️ (ASR, forced alignment, and optional **speaker diarization** via pyannote), and **summarize** with a local LLM through **Ollama** 🦙—without sending audio or transcripts to the cloud by default.

The UI is **Qt Quick (QML)** on **PySide6** 🐍; Python owns persistence, AI adapters, and background work (`QThread` workers) so the interface stays responsive.

---

**📑 Table of contents**

- [Additional documentation](#additional-documentation) — *links to `docs/`, `packaging/offline/`, and CONTRIBUTING.*
- [Breaking changes](#breaking-changes) — *SQLite migrations, deprecated env paths, and artifact layout changes.*
- [Project overview](#project-overview) — *sessions, audio, STT, summarization, artifacts, prompts, pipeline, UI language.*
- [Models and services](#models-and-services) — *ASR, alignment, diarization, and Ollama summarization stack.*
- [Dependencies](#dependencies) — *Python packages, external binaries, and GPU notes.*
  - [Python](#dependencies-python) — *version, `pip install`, package roles, dev tools, tests.*
  - [External tools](#dependencies-external-tools) — *Ollama, FFmpeg, optional GPU.*
  - [PyTorch and CUDA](#dependencies-pytorch-and-cuda) — *CUDA-capable `torch`, verification command, mock mode.*
- [Install](#install) — *clone, venv, dependencies, FFmpeg & Ollama, optional `.env`.*
- [Offline USB bundle](#offline-docker-handoff) — *Path A: PyInstaller host client + headless WhisperX containers via USB.*
- [Configuration: `.env`](#configuration-env) — *how `python-dotenv` loads the repo-root `.env` and precedence vs the OS environment.*
- [`constants.py` (summary)](#constants-py-summary) — *settings keys, defaults, enums, and extension lists.*
- [Configuration (environment variables)](#configuration-environment-variables) — *full `MEETING_ASSISTANT_*` reference from `config.py`.*
  - [Backend mode, debug, trace](#env-backend-mode-debug-trace) — *mock backend, debug UI, trace verbosity.*
  - [Ollama](#env-ollama) — *base URL, host, port, model name.*
  - [Hugging Face token (real transcription)](#env-hugging-face-token) — *token env vars and in-app Settings override.*
  - [Whisper / WhisperX (ASR, alignment, device)](#env-whisper-whisperx) — *model, cache, language, beam size, device, batch, compute types.*
  - [Data paths and outputs](#env-data-paths-and-outputs) — *`DATA_DIR`, SQLite path, forced output root, default folders.*
  - [Mock tuning](#env-mock-tuning) — *artificial delays in mock mode.*
  - [FFmpeg path and audio preprocessing](#env-ffmpeg-audio-preprocessing) — *decode path, prep chain, loudnorm, timeouts.*
- [Where configuration lives (layers)](#where-configuration-lives-layers) — *env vs SQLite vs per-message prompts vs code constants.*
- [How to run](#how-to-run) — *`python main.py`, prerequisites checklist, mock-mode one-liner.*
- [How to use (typical flow)](#how-to-use-typical-flow) — *sessions, record/import, prompts, pipeline, artifacts, summarize-only, stateless LLM.*
- [Current pipeline (detail)](#current-pipeline-detail) — *prepare → transcribe → persist → summarize → persist; mock behavior.*
- [Prompt composition](#prompt-composition) — *how Whisper `initial_prompt` and LLM system/user messages are built.*
  - [Arabic meetings with English technical terms](#arabic-meetings-with-english-technical-terms) — *glossary, `WHISPER_LANGUAGE`, alignment language, jargon normalize.*
- [In-app settings (persisted)](#in-app-settings-persisted) — *what is stored in SQLite when not in mock mode.*
- [UI language, RTL, and translations](#ui-language-rtl-and-translations) — *toolbar locale, RTL, catalog and optional `.qm`.*
- [Architecture (high level)](#architecture-high-level) — *QML facade, ports, adapters, workers, composition root.*
- [Project structure](#project-structure) — *repository tree (`src`, `tests`, `docs`, scripts).*
- [Development](#development) — *`PYTHONPATH`, `pytest`, optional Ruff.*
- [Troubleshooting](#troubleshooting) — *QML style, Ollama host, cache, GPU, TorchCodec, HF token, pytest imports.*
- [License](#license) — *Apache 2.0.*
- [Contributing](#contributing) — *see [CONTRIBUTING.md](CONTRIBUTING.md) for sync rules and PR checklist.*

---

<a id="additional-documentation"></a>

**📚 More documentation**

- 🇸🇦 [docs/INSTALLATION_AR.md](docs/INSTALLATION_AR.md) — دليل عربي للتثبيت ونقل المشروع (Windows، Whisper، Ollama، حزمة USB Path A).
- 📄 [docs/PROJECT_DESCRIPTION.md](docs/PROJECT_DESCRIPTION.md) — short consultation-ready overview (purpose, stack, constraints).
- 📋 [docs/SRS.md](docs/SRS.md) — Software Requirements Specification (intent and architecture).
- 🎤 [docs/Feature SRS - Speaker Diarization and Alignment.md](docs/Feature%20SRS%20-%20Speaker%20Diarization%20and%20Alignment.md) — diarization and alignment addendum.
- 🤝 [CONTRIBUTING.md](CONTRIBUTING.md) — development setup, documentation sync rules, PR checklist.
- 🧊 [docs/OFFLINE_DOCKER_HANDOFF.md](docs/OFFLINE_DOCKER_HANDOFF.md) — USB/offline Path A packaging and operator runbook.
- 📦 [packaging/offline/README.md](packaging/offline/README.md) — build scripts, Dockerfiles, and USB bundle layout.

---

<a id="breaking-changes"></a>

## ⚠️ Breaking changes

- **🗄️ SQLite:** Deprecated **`app_settings`** keys (`global_default_prompt`, `prompt_bundle_v2_applied`) are **deleted on startup**. The legacy **`sessions.chat_prompt`** column is **dropped** when SQLite supports `DROP COLUMN` (3.35+). Older DB files missing newer message/session columns still get the usual **`ALTER TABLE … ADD COLUMN`** pass so the app can open them. Prefer a **fresh** `meetings.db` when you want a completely clean file; back up first if you need history.
- **📁 `MEETING_ASSISTANT_TRANSCRIPTS`** is no longer supported. **New runs** write session audio and `.txt` artifacts (transcript and summary) under **`<meeting_output_root>/sessions/<artifacts_slug>/`** only. The types in `resolve_meeting_output_dirs` still expose logical `recordings/`, `transcripts/`, and `summaries/` under the output root (e.g. for tests and older helpers), but the GUI pipeline uses the per-session folder above—not a root-level `transcripts/` directory for those files.

---

<a id="project-overview"></a>

## 📌 Project overview

| Area | What it does |
|------|----------------|
| **💬 Sessions** | Chat-style sessions with local history (SQLite when not in mock mode). |
| **🎵 Audio** | Microphone capture (Qt Multimedia, when available) and file upload / drag-and-drop. |
| **🎙️ Speech-to-text** | **WhisperX** (faster-whisper + forced alignment; optional **pyannote diarization**, **off by default**). When diarization is enabled, a **Hugging Face access token** is required (Hub-gated pyannote stack). When disabled, transcription runs without a token and emits timestamp-only lines (`[MM:SS - MM:SS]: …`). Toggle in **Settings** or set **`MEETING_ASSISTANT_SPEAKER_DIARIZATION`** (`1` / `0`). Store the HF token in **Settings** (recommended) or set **`MEETING_ASSISTANT_HF_TOKEN`** (or `HF_TOKEN` / `HF_ACCESS_TOKEN` / `HUGGING_FACE_HUB_TOKEN`). Accept **pyannote** model conditions on the Hub when using diarization. |
| **🦙 Summarization** | **Ollama** `/api/chat` with a configurable model and composed system prompt. |
| **📂 Artifacts** | Per-session folder under `<output_root>/sessions/<name>/` (audio, transcript `.txt`, summary `.txt`). |
| **✏️ Prompts** | Separate **global Whisper context** (biases transcription) and **global LLM system** text (summarization), plus optional **per-recording** overrides stored with the session. |
| **🔄 Pipeline** | **`TranscriptionWorker`** then **`SummarizeWorker`** (after you confirm speaker names when diarization finds speakers). Stopping mid-run may leave a **partial transcript**; if summarization fails after a successful transcript, the app can still show transcript text with an **error placeholder** for the summary. |
| **🌐 UI language** | **Arabic** or **English** chrome (toolbar toggle); persisted as `ui_language` (`ar` / `en`). Default first-run UI language is **`ar`** ([`DEFAULT_UI_LANGUAGE`](src/meeting_assistant/core/constants.py)). Arabic uses **RTL** layout. Strings: [`src/meeting_assistant/i18n/ar_catalog.py`](src/meeting_assistant/i18n/ar_catalog.py); optional override [`src/meeting_assistant/translations/meeting_assistant_ar.qm`](src/meeting_assistant/translations/). Independent of `MEETING_ASSISTANT_WHISPER_LANGUAGE` (transcription language). |

**👥 Speaker diarization** (optional, default off) uses WhisperX and pyannote when enabled. Transcripts use lines like `SPEAKER_00 [MM:SS - MM:SS]: …`. After transcription, the chat can ask for **display names**; confirming **rewrites** the transcript `.txt` with those names and runs the summary. Mappings are stored in SQLite (`session_speakers`). When diarization is off, transcripts use `[MM:SS - MM:SS]: …` and skip the speaker-naming step.

On **Windows** 🪟, `main.py` calls **`ensure_nvidia_pip_dll_directories()`** so CUDA runtime libraries shipped via the pinned **`nvidia-*`** wheels are discoverable when WhisperX uses the GPU.

---

<a id="models-and-services"></a>

## 🤖 Models and services

| Piece | Technology | Notes |
|--------|------------|--------|
| **🎙️ ASR** | WhisperX + **CTranslate2** (faster-whisper–compatible weights) | Default size key `large-v3` → Hub repo `Systran/faster-whisper-large-v3`. Other keys and custom `org/name` repos: see `FASTER_WHISPER_HF_REPOS` in [`src/meeting_assistant/config.py`](src/meeting_assistant/config.py). Inference uses **local files only** at load (`local_files_only=True`); download via UI or pre-populate cache under `MEETING_ASSISTANT_WHISPER_CACHE`. |
| **📐 Alignment** | WhisperX `load_align_model` / `align` | Alignment language: `MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE` (default **`ar`** in code; set `auto` / `none` / empty to follow **ASR-detected** language). |
| **👥 Diarization & speaker assignment** | WhisperX `DiarizationPipeline` + `assign_word_speakers` | Optional (Settings / `MEETING_ASSISTANT_SPEAKER_DIARIZATION`, default **off**). pyannote stack behind WhisperX; **HF token required only when diarization is enabled**. Exact checkpoint IDs depend on your installed **`whisperx`** version. |
| **🦙 Summarization** | **Ollama** `POST /api/chat` | Default model in code: `gemma4:e4b128k` (`MEETING_ASSISTANT_OLLAMA_MODEL`). |

---

<a id="dependencies"></a>

## 📦 Dependencies

<a id="dependencies-python"></a>

### 🐍 Python

- **Python 3.11+** (matches [`pyproject.toml`](pyproject.toml) `requires-python`; 3.12 is a good default).
- Install runtime packages from the repo root:

```bash
pip install -r requirements.txt
```

| Package (from `requirements.txt`) | Role |
|-----------------------------------|------|
| **PySide6** 🖼️ | QML / Qt Quick desktop UI |
| **python-dotenv** 📄 | Optional load of repo-root `.env` (see [Configuration: `.env`](#configuration-env) ) |
| **whisperx** 🎙️ | ASR, alignment, diarization orchestration |
| **torch** 🔥 | Backend for WhisperX (PyPI wheel is often **CPU-only**; see GPU note below) |
| **huggingface_hub** 🤗 | Model download / cache |
| **httpx** 🌐 | Ollama HTTP client |
| **nvidia-*** (pinned) 🖥️ | CUDA 12 runtime pieces on Windows for GPU stacks |

**🧪 Dev / lint (optional):** from repo root, `pip install '.[dev]'` then `ruff check src tests` (Ruff config in [`pyproject.toml`](pyproject.toml)).

**✅ Tests:** `pytest` is not pinned in `requirements.txt`; `pip install pytest` to run the suite. Use **`PYTHONPATH`** pointing at **`src`** (see [Development](#development)).

<a id="dependencies-external-tools"></a>

### 🔧 External tools

- 🦙 **[Ollama](https://ollama.com/)** — local LLM server (`/api/chat`).
- 🎬 **[FFmpeg](https://ffmpeg.org/)** — required for real transcription (decode + optional pre-ASR prep). Resolution: **`MEETING_ASSISTANT_FFMPEG_PATH`**, `ffmpeg` next to the app executable, then **`PATH`**. Example (Windows): `winget install ffmpeg`.
- 🖥️ **GPU (optional)** — CUDA improves WhisperX throughput; CPU fallback when acceleration fails. Install a **CUDA-enabled PyTorch** into the **same** venv if you need GPU (see below).

<a id="dependencies-pytorch-and-cuda"></a>

### 🔥 PyTorch and CUDA

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

**🧪 Mock mode:** set `MEETING_ASSISTANT_MOCK=1` — FFmpeg is not required.

---

<a id="install"></a>

## 🚀 Install

1. 📥 **Clone** the repository and enter the project directory (folder that contains `main.py`).

2. 🐍 **Create a virtual environment**

```bash
python -m venv .venv
```

Activate:

- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source .venv/bin/activate`

3. 📦 **Install Python dependencies**

```bash
pip install -r requirements.txt
```

4. 🎬 **Install FFmpeg** and 🦙 **Ollama** on the host, then provide the model named in `MEETING_ASSISTANT_OLLAMA_MODEL`. The default `gemma4:e4b128k` is a **derived** long-context model — create it from the base `gemma4:e4b` (don't `ollama pull gemma4:e4b128k`):

```bash
ollama pull gemma4:e4b
printf 'FROM gemma4:e4b\nPARAMETER num_ctx 131072\n' > Modelfile
ollama create gemma4:e4b128k -f Modelfile
```

5. **Optional:** 📋 copy [`.env.example`](.env.example) to **`.env`** in the repo root and set variables (never commit `.env`).

---

<a id="configuration-env"></a>

## ⚙️ Configuration: `.env`

At import time, [`src/meeting_assistant/config.py`](src/meeting_assistant/config.py) loads **`.env`** from the **repository root** (same folder as `main.py`) using **python-dotenv**, with **`override=False`**: variables already set in the OS environment **win** over `.env`.

If `python-dotenv` is missing, `.env` is skipped (the app still reads the real environment).

**Full variable reference:** tables below and the source in `config.py`. [`.env.example`](.env.example) lists common keys with comments.

---

<a id="constants-py-summary"></a>

## 📄 `src/meeting_assistant/core/constants.py` (summary)

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
| **`SETTINGS_KEY_SPEAKER_DIARIZATION_ENABLED`** | `speaker_diarization_enabled` in SQLite (`1` / `0`; default off). |
| **`SETTINGS_DEPRECATED_SQLITE_KEYS`** | Legacy keys stripped on startup if present: `global_default_prompt`, `prompt_bundle_v2_applied`. |
| **`DEFAULT_UI_LANGUAGE`** | First-run UI chrome default: **`ar`**. |
| **`DEFAULT_SUMMARY_PROMPT`** | Default Arabic structured summarization instructions (LLM system). |
| **`DEFAULT_WHISPER_CONTEXT`** | Default domain / glossary bias for Whisper. |
| **`DEFAULT_RECORDING_LLM_INSTRUCTIONS`** | Pre-filled per-recording LLM hint in the chat UI (user-editable). |
| **`DEFAULT_RECORDING_WHISPER_CONTEXT`** | Pre-filled per-recording Whisper context in the chat UI. |

---

<a id="configuration-environment-variables"></a>

## 🎛️ Configuration (environment variables)

Most variables below are read in **`src/meeting_assistant/config.py`**. **`MEETING_ASSISTANT_OUTPUT_ROOT`** is read in **`src/meeting_assistant/services/output_paths.py`** (meeting artifact root precedence). Defaults match the current codebase.

<a id="env-backend-mode-debug-trace"></a>

### 🧩 Backend mode, debug, trace

| Variable | Default | Meaning |
|----------|---------|---------|
| `MEETING_ASSISTANT_MOCK` | `0` | If true: mock STT/LLM and in-memory sessions. If false: SQLite + WhisperX + Ollama. |
| `MEETING_ASSISTANT_DEBUG` | `0` | Extra debug UI where implemented (`DEBUG_UI`). |
| `MEETING_ASSISTANT_TRACE_LEVEL` | `0` | Terminal trace verbosity **0–3** (0 = default logging; 1 = main pipeline; 2 = sub-steps/I/O; 3 = fine-grained). If set, overrides `MEETING_ASSISTANT_VERBOSE`. |
| `MEETING_ASSISTANT_VERBOSE` | *(unset)* | Alias for the same **0–3** scale as `TRACE_LEVEL` when `TRACE_LEVEL` is unset. |

<a id="env-ollama"></a>

### 🦙 Ollama

| Variable | Default | Meaning |
|----------|---------|---------|
| `MEETING_ASSISTANT_OLLAMA_BASE_URL` | *(unset)* | If non-empty, **full** base URL (e.g. `http://127.0.0.1:11434`). Overrides host/port. No trailing slash. |
| `MEETING_ASSISTANT_OLLAMA_HOST` | **`localhost`** on Windows; **`127.0.0.1`** on Linux/macOS | Host only. |
| `MEETING_ASSISTANT_OLLAMA_PORT` | `11434` | HTTP port. |
| `MEETING_ASSISTANT_OLLAMA_MODEL` | `gemma4:e4b128k` | Model name for `/api/chat`. |

If `MEETING_ASSISTANT_OLLAMA_BASE_URL` is unset, the client uses `http://{OLLAMA_HOST}:{OLLAMA_PORT}`.

<a id="env-hugging-face-token"></a>

### 🤗 Hugging Face token (speaker diarization)

Required **only when speaker diarization is enabled** (off by default). Enable diarization in Settings or set `MEETING_ASSISTANT_SPEAKER_DIARIZATION=1`.

The process reads the **first non-empty** value among (after `.env` load):

`MEETING_ASSISTANT_HF_TOKEN`, `HF_ACCESS_TOKEN`, `HUGGING_FACE_HUB_TOKEN`, `HF_TOKEN`.

In-app **Settings** can override env when the stored token is non-empty (see `resolve_hf_access_token` in [`src/meeting_assistant/services/hf_token.py`](src/meeting_assistant/services/hf_token.py)).

| Variable | Default | Meaning |
|----------|---------|---------|
| `MEETING_ASSISTANT_SPEAKER_DIARIZATION` | `0` | If `1` / `true` / `on`, run pyannote diarization (alignment still runs). Persisted Settings override after first run. |

<a id="env-whisper-whisperx"></a>

### 🎙️ Whisper / WhisperX (ASR, alignment, device)

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

<a id="env-data-paths-and-outputs"></a>

### 📂 Data paths and outputs

| Variable | Default | Meaning |
|----------|---------|---------|
| `MEETING_ASSISTANT_DATA_DIR` | OS-specific (see below) | App data root; SQLite lives here unless `MEETING_ASSISTANT_DB` overrides. |
| `MEETING_ASSISTANT_DB` | `{DATA_DIR}/meetings.db` | SQLite path. |
| `MEETING_ASSISTANT_OUTPUT_ROOT` | *(unset)* | If set, **forces** meeting output root; GUI sessions use `sessions/` beneath it (overrides in-app custom folder). Read in **`output_paths.py`**, not `config.py`. |

**Default `DATA_DIR`** when `MEETING_ASSISTANT_DATA_DIR` is unset (`_local_data_dir()` in `config.py`):

- **Windows:** `%LOCALAPPDATA%\MeetingAssistant` (when `LOCALAPPDATA` is set), else `~/.local/share/MeetingAssistant`.
- **Linux/macOS:** `$XDG_DATA_HOME/MeetingAssistant` when `XDG_DATA_HOME` is set; else **`~/.local/share/MeetingAssistant`**.

**Default meeting outputs** when neither env nor in-app override applies: **`{PROJECT_ROOT}/meeting_outputs`** with per-session folders under **`sessions/`**.

<a id="env-mock-tuning"></a>

### 🎭 Mock tuning

| Variable | Default | Meaning |
|----------|---------|---------|
| `MEETING_ASSISTANT_MOCK_DELAY` | `0.45` | Artificial delay (seconds) in mock transcription/summarization. |

<a id="env-ffmpeg-audio-preprocessing"></a>

### 🎬 FFmpeg path and audio preprocessing

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

<a id="where-configuration-lives-layers"></a>

## 🧱 Where configuration lives (layers)

| Layer | Location | What it controls |
|--------|-----------|------------------|
| **🌍 Environment / `.env`** | `config.py` | Feature flags, Ollama, Whisper, paths, mock timing, trace level. |
| **⚙️ In-app settings** | SQLite via `SettingsController` | Global LLM system text, global Whisper context, optional meeting output root, speaker diarization toggle, HF token (`SETTINGS_KEY_HF_ACCESS_TOKEN`). `MEETING_ASSISTANT_OUTPUT_ROOT` still wins over the custom folder. |
| **🌐 UI locale** | SQLite `app_settings` (`ui_language`) | `ar` / `en`; `LocaleController`. |
| **✏️ Per-session / per-recording prompts** | Message/session rows | Optional recording-level Whisper + LLM instructions; composed at pipeline time. |
| **📄 Constants** | [`src/meeting_assistant/core/constants.py`](src/meeting_assistant/core/constants.py) | Extensions, settings keys, default prompts, enums. |
| **📂 Output layout** | [`src/meeting_assistant/services/output_paths.py`](src/meeting_assistant/services/output_paths.py) | Resolution of meeting file paths vs env overrides. |

---

<a id="how-to-run"></a>

## ▶️ How to run

From the repository root (directory containing **`main.py`**):

```bash
python main.py
```

On **Windows**, you can use **`run.ps1`** or **`run.bat`** instead — they activate **`.venv`** if present, then run **`main.py`**.

`main.py` adds `src` to `sys.path` and loads QML from `src/meeting_assistant/qml/`.

**✅ Checklist (real backend, default):**

1. 🦙 **Ollama** running with the model you configure (`MEETING_ASSISTANT_OLLAMA_MODEL`, default `gemma4:e4b128k`).
2. 🤗 **Hugging Face token** set (Settings or env) **if speaker diarization is enabled**; pyannote terms accepted on the Hub.
3. 🎙️ **Whisper CT2** snapshot complete under `MEETING_ASSISTANT_WHISPER_CACHE` (in-app download when using the real backend).
4. 🎬 **FFmpeg** discoverable (see above).

**🧪 Mock mode (no AI stack):**

```powershell
$env:MEETING_ASSISTANT_MOCK="1"
python main.py
```

---

<a id="offline-docker-handoff"></a>

## 🧊 Offline USB bundle (Path A)

Use this when you need to hand over the app on USB and run **without internet** on the target laptop.

**Architecture:** native Windows GUI (`MeetingAssistant.exe` via PyInstaller) + headless WhisperX in Docker + Ollama in Docker (model baked in). The only prerequisite on the target is **Docker Desktop**. GPU is best-effort with automatic CPU fallback. All packaging lives under [`packaging/offline/`](packaging/offline/).

Quick flow:

```powershell
# Source machine (online): build images, PyInstaller exe, assemble USB folder
.\packaging\offline\scripts\build_usb_bundle.ps1 -OutputDir .\packaging\offline\usb-bundle

# Target machine (offline): load images, start inference, open desktop app
.\install_from_usb.ps1
.\launch_host_client.ps1

# Validate bundle after install
.\accept_offline_bundle.ps1
```

Key files in the USB bundle:

- `RUNBOOK.txt` — operator instructions (read this first on the target machine)
- `install_from_usb.ps1` / `launch_host_client.ps1`
- `images/*.tar` — GPU + CPU WhisperX images and the Ollama image (all models baked in)
- `compose/compose.yml` (base) + `compose/compose.gpu.yml` (GPU override)
- `.env.bundle` — Ollama URL, Whisper API port, persistent data paths

Defaults: Whisper `large-v3-turbo`, alignment `ar`, API port `18080`, Ollama `http://127.0.0.1:11434` with derived model `gemma4:e4b128k` (`num_ctx` 131072, from base `gemma4:e4b`).

Detailed runbook: [`docs/OFFLINE_DOCKER_HANDOFF.md`](docs/OFFLINE_DOCKER_HANDOFF.md) and [`packaging/offline/README.md`](packaging/offline/README.md).

---

<a id="how-to-use-typical-flow"></a>

## 📖 How to use (typical flow)

1. 💬 **Create or open a session** in the sidebar.
2. 🎤 **Record** audio or **upload** / drag-and-drop a supported file (see `AUDIO_EXTENSIONS` in `constants.py`).
3. **Optional:** ⚙️ edit global prompts in **Settings**, or per-recording Whisper / LLM hints on the message before send.
4. ▶️ **Process:** the app runs **transcription** (WhisperX: ASR → align → diarize when token is valid), writes a **transcript `.txt`**, and may prompt for **speaker display names**; after confirm, it runs **summarization** via Ollama and writes a **summary `.txt`**.
5. 📂 **Artifacts** live under `{meeting_output_root}/sessions/{artifacts_slug}/` (default root: `meeting_outputs` under the project).

**📝 Summarize-only:** from an existing transcript, only Ollama summarization runs (no new ASR).

There is **no cross-session LLM memory** 📭: each summary uses only that run’s transcript and composed prompts.

---

<a id="current-pipeline-detail"></a>

## 🔄 Current pipeline (detail)

1. 🧩 **Prepare** — Resolve session output folder under `sessions/`, build prompt snapshot (global + per-recording).
2. 🎙️ **Transcribe** — **`TranscriptionWorker`**: WhisperX with `initial_prompt` from composed Whisper context. Optional **`MEETING_ASSISTANT_TRANSCRIPT_JARGON_NORMALIZE=1`**: extra Ollama pass using the same glossary text. Emits **`finished_raw(transcript, txt_path, speaker_keys)`**.
3. 👥 **Speaker intercept (when keys exist)** — Pipeline **pauses**; optional display-name mapping in the chat UI. **Confirm** rewrites the transcript `.txt` and SQLite **`session_speakers`**, then starts **`SummarizeWorker`**. No keys → summarization runs immediately.
4. 🦙 **Summarize** — Ollama: **system** = composed LLM prompt; **user** = transcript only.
5. 📝 **Persist summary** — `.txt` + chat bubble.

**🧪 Mock mode:** artificial delays; in-memory sessions; no real Whisper/Ollama/SQLite persistence paths for AI.

---

<a id="prompt-composition"></a>

## 💬 Prompt composition

Merged in [`src/meeting_assistant/services/prompt_composition.py`](src/meeting_assistant/services/prompt_composition.py); accessors in [`src/meeting_assistant/services/prompts.py`](src/meeting_assistant/services/prompts.py).

- **🎙️ Whisper `initial_prompt`** — Global Whisper context + per-recording Whisper context (suffix preserved if over ~1800 characters).
- **🦙 LLM system** — Global LLM system + per-recording summarization instructions.
- **📄 LLM user** — Transcript text only.

<a id="arabic-meetings-with-english-technical-terms"></a>

### 🌍 Arabic meetings with English technical terms

1. Put a **mixed glossary** in global and/or per-recording **Whisper** context (Arabic plus exact Latin spellings).
2. Prefer **`MEETING_ASSISTANT_WHISPER_LANGUAGE=auto`** for code-switching when appropriate.
3. If alignment drifts under auto ASR, set **`MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE=ar`** explicitly (this is already the **code default**; use `auto` to follow detection).
4. Optional **`MEETING_ASSISTANT_TRANSCRIPT_JARGON_NORMALIZE=1`** for an Ollama “technical editor” pass.

---

<a id="in-app-settings-persisted"></a>

## ⚙️ In-app settings (persisted)

When not in mock mode: global LLM system prompt, global Whisper context, optional meeting files folder, speaker diarization toggle, HF token, UI language — stored in SQLite (`app_settings` keys from `constants.py`). Edited via **`app.settingsController`** and **`app.localeController`** in QML.

---

<a id="ui-language-rtl-and-translations"></a>

## 🌐 UI language, RTL, and translations

- Toolbar toggle **English** ↔ **العربية** 🔤; persisted as `ui_language`.
- **Default** first run: **Arabic** (`DEFAULT_UI_LANGUAGE`).
- **RTL** for Arabic; mirrored chat alignment as implemented.
- **📚 Catalog:** [`src/meeting_assistant/i18n/ar_catalog.py`](src/meeting_assistant/i18n/ar_catalog.py).
- **📦 Optional `.qm`:** `meeting_assistant_ar.qm` under `src/meeting_assistant/translations/` loads after the catalog.

---

<a id="architecture-high-level"></a>

## 🏗️ Architecture (high level)

- **UI:** 🖼️ QML [`src/meeting_assistant/qml/Main.qml`](src/meeting_assistant/qml/Main.qml) → context property **`app`** (`AppFacade`).
- **Ports:** 🔌 [`src/meeting_assistant/ports/`](src/meeting_assistant/ports/) — session, transcription, summarization contracts.
- **Adapters:** 🔗 [`src/meeting_assistant/adapters/`](src/meeting_assistant/adapters/) — SQLite, WhisperX, Ollama, mocks. Wiring: **`app_context.build_app_facade()`** from **`config.USE_MOCK_BACKEND`**.
- **Workers:** ⚙️ [`src/meeting_assistant/workers/`](src/meeting_assistant/workers/) — `TranscriptionWorker`, `SummarizeWorker`, `ModelDownloadWorker`.
- **Composition:** 🧩 [`src/meeting_assistant/app_context.py`](src/meeting_assistant/app_context.py) builds the facade after `QQmlApplicationEngine` so translators install before/during QML load.

---

<a id="project-structure"></a>

## 📁 Project structure

```text
meeting_summary/
├── main.py                          # Entry: DLL paths (Windows), logging, QML, context property `app`
├── run.ps1                          # PowerShell launcher (activates .venv, runs main.py)
├── run.bat                          # Windows batch launcher
├── requirements.txt                 # Runtime pip dependencies
├── pyproject.toml                   # Ruff, requires-python, optional dev extras
├── LICENSE                          # Apache License 2.0
├── .env.example                     # Example environment (copy to .env; do not commit secrets)
├── docs/
│   ├── SRS.md
│   ├── PROJECT_DESCRIPTION.md
│   ├── INSTALLATION_AR.md
│   ├── OFFLINE_DOCKER_HANDOFF.md
│   └── Feature SRS - Speaker Diarization and Alignment.md
├── packaging/
│   └── offline/                   # Path A USB bundle (Docker images + PyInstaller host client)
│       ├── README.md              # Operator/dev runbook (copied as RUNBOOK.txt on USB)
│       ├── images/                # Dockerfile.gpu, Dockerfile.cpu, Dockerfile.ollama
│       ├── compose/                 # compose.yml (base), compose.gpu.yml (override)
│       ├── scripts/               # build_usb_bundle.ps1, install_from_usb.ps1, …
│       └── host-client/           # PyInstaller spec + build_host_client.ps1
├── README.md
├── CONTRIBUTING.md                # Dev setup, doc sync rules, PR checklist
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
│   ├── test_diarization_settings.py
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

<a id="development"></a>

## 🛠️ Development

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

<a id="troubleshooting"></a>

## 🔧 Troubleshooting

- **QML on Windows:** `main.py` sets `QT_QUICK_CONTROLS_STYLE=Basic` for consistent styling 🎨.
- **Ollama:** Use `MEETING_ASSISTANT_OLLAMA_BASE_URL` or adjust host/port defaults (Windows **`localhost`**, Linux/macOS **`127.0.0.1`**).
- **Whisper cache incomplete:** Fill `MEETING_ASSISTANT_WHISPER_CACHE` or use in-app download; check `MEETING_ASSISTANT_WHISPER_MIN_BIN_BYTES` for custom repos 📥.
- **GPU errors:** Try `MEETING_ASSISTANT_WHISPER_DEVICE=cpu` or tune `MEETING_ASSISTANT_WHISPER_COMPUTE_TYPES`; Windows CUDA DLLs: `nvidia-*` wheels + `nvidia_windows_dlls.py`.
- **Offline USB bundle:** See [Offline USB bundle](#offline-docker-handoff). Run `accept_offline_bundle.ps1` after install to validate API health and offline guards. On Hyper-V Docker Desktop, GPU compose may fail — CPU fallback is automatic.
- **TorchCodec / pyannote warning on Windows:** Pip TorchCodec may lack native DLLs; WhisperX still decodes via FFmpeg when FFmpeg resolves. Benign warning filtered at startup in `main.py` ⚠️.
- **HF token:** Required when **speaker diarization** is enabled (Settings or env); accept Hub model terms 🤗. Diarization is off by default — enable it in Settings or set `MEETING_ASSISTANT_SPEAKER_DIARIZATION=1` when you need speaker labels.
- **pytest import errors:** Set `PYTHONPATH` to **`src`** 🧪.

---

<a id="license"></a>

## 📜 License

This project is licensed under the **Apache License 2.0** 📜 — see [LICENSE](LICENSE).

---

<a id="contributing"></a>

## 🤝 Contributing

Issues and pull requests are welcome. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for development setup, documentation sync rules, and the PR checklist.
