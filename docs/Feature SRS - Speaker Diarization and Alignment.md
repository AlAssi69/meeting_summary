Here is the Feature Specification (SRS Addendum) for the Speaker Diarization and Alignment feature.

This document is designed to act as an extension to existing `SRS.md`, adhering to established architectural patterns (Ports/Adapters, QThread workers, and modularity).

---

## Implementation status

**Shipped in the current codebase.** High-level wiring:

- **Transcription:** `WhisperXAdapter` / WhisperX pipeline (ASR → alignment → diarization when a Hugging Face token is available).
- **Worker split:** `TranscriptionWorker` writes the transcript and emits **`finished_raw(transcript, txt_path, speaker_keys)`**; `ChatController` handles the intercept UI, optional transcript rewrite with user labels, then starts **`SummarizeWorker`** for a **single** Ollama summary of the (possibly relabeled) transcript.
- **Persistence:** SQLite table **`session_speakers`**; Settings key **`hf_access_token`** (see `SETTINGS_KEY_HF_ACCESS_TOKEN` in `src/meeting_assistant/core/constants.py`), with environment fallbacks documented in the README.

The sections below retain the original design intent; **§5** records the historical rollout as **completed** phases.

---

# Feature Specification: Speaker Diarization & Alignment

## 1. Introduction

**1.1 Purpose**

This specification documents **speaker diarization** and **word-level timestamp alignment** in the Local AI Meeting Assistant: structured, multi-speaker transcript lines and a deliberate **halt** between transcription and summarization so operators can map `SPEAKER_XX` labels to display names when desired.

**1.2 Priority Matrix**

* **Highest Priority:** Transcription and speaker attribution accuracy (forced phoneme-level alignment).
* **Secondary Priority:** Seamless daily User Experience (UX) post-setup.
* **Accepted Trade-offs:** Increased disk footprint, high RAM/VRAM utilization, and initial setup friction (Hugging Face token configuration).

**1.3 Target Output Format**

The required baseline format for the generated transcript artifacts and the Ollama context window is:

```text
SPEAKER_00 [00:00 - 00:15]: Let's start the meeting.
SPEAKER_01 [00:15 - 00:22]: I agree, let's look at the agenda.

```

---

## 2. Architectural Updates

**2.1 Dependency Additions**

* **`whisperx`:** Wraps faster-whisper–compatible ASR, Wav2Vec2 forced alignment, and delegates diarization.
* **`pyannote.audio`:** Unsupervised speaker clustering. Requires user authentication via Hugging Face.

**2.2 Pipeline worker split (“halt” architecture)**

The former monolithic transcribe→summarize path was **decoupled** to support the UI intercept pattern:

1. **`TranscriptionWorker` (Phase A):**
   * Executes the WhisperX pipeline (Transcribe → Align → Diarize).
   * Persists the raw transcript with `SPEAKER_XX` tags when diarization runs.
   * Emits **`finished_raw`** with transcript text, transcript file path, and extracted speaker keys, then **terminates**.

2. **The intercept (UI state):** The autonomous pipeline **halts**. The UI collects optional `SPEAKER_XX` → display name mappings (and may offer short audio samples).

3. **`SummarizeWorker` (Phase B):** Started by the UI after mapping is confirmed (or immediately when no speakers need naming).
   * Applies the mapping to the transcript text (and transcript file) where implemented.
   * Builds the composed LLM prompt and runs the Ollama HTTP request for **one** session summary.

---

## 3. Data Model & Persistence (SQLite schema)

**3.1 Table: `session_speakers`**

Stores the mapping of generic speaker tags to user-defined names for a specific session.

* `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
* `session_id` (TEXT, FOREIGN KEY to `sessions(id)` ON DELETE CASCADE)
* `speaker_key` (TEXT) — e.g. `"SPEAKER_00"`
* `speaker_name` (TEXT) — e.g. `"Eng. Mhd."`
* UNIQUE(`session_id`, `speaker_key`)

**3.2 `app_settings`**

* Key **`hf_access_token`** (TEXT) — Stores the user’s Hugging Face token for `pyannote.audio` (empty string allowed; env vars remain fallbacks — see README).

---

## 4. User Interface (QML)

**4.1 Global Settings**

* **Authentication field:** A secure `TextField` (echoMode: Password) in the settings menu for the **Hugging Face access token**, with validation feedback where implemented.

**4.2 Chat interface: intercept card**

When `ChatController` receives **`TranscriptionWorker.finished_raw`** with one or more speaker keys, it injects the intercept UI into the chat feed (rather than only a standard assistant bubble):

* **Header:** e.g. diarization complete / N speakers identified.
* **List view:** Detected `SPEAKER_XX` rows with editable display names.
* **Optional:** Short per-speaker audio sample playback to disambiguate voices.
* **Action:** Confirm and continue — triggers summarization (`SummarizeWorker`) after any relabeling and file rewrite.

---

## 5. Implementation phases (historical — completed)

These phases were used to land the feature on `main`; all are **done**.

### Phase 1: Core backend integration — **Done**

* **Objective:** Integrate WhisperX and verify target output formatting.
* **Outcome:** WhisperX-backed transcription port, `SPEAKER_XX [HH:MM - HH:MM]:` lines when diarization succeeds, environment-based HF access for early bring-up.

### Phase 2: Schema migration & settings UI — **Done**

* **Objective:** Persist HF token and speaker mappings.
* **Outcome:** `session_speakers` table, `hf_access_token` in `app_settings`, Settings/QML exposure, `config` / repository reads with env fallback.

### Phase 3: Intercept & mapping UI — **Done**

* **Objective:** Halt after transcription, capture names, then summarize.
* **Outcome:** `TranscriptionWorker` / `SummarizeWorker` split, QML intercept flow wired from `finished_raw`, SQLite persistence of mappings, transcript rewrite before Ollama for the standard **single-summary** workflow.
