# Mémoire des Territoires – Project Overview

This document summarizes the **project structure**, **app workflow**, and **TTS (text-to-speech) process** for quick reference and debugging.

---

## 1. Project structure

```
memoiredesterritoires/
├── app/                          # React SPA (TypeScript, Vite, TanStack Query, Zustand)
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                # Routes + Layout (header, StepNavigator, ChatPanel)
│   │   ├── api/client.ts          # REST API client (sessions, scenario-audio, etc.)
│   │   ├── views/                 # Step-specific views
│   │   │   ├── ProjectSelectionView.tsx
│   │   │   ├── ProjectDetailsView.tsx
│   │   │   ├── AudioSelectionView.tsx
│   │   │   ├── ScenarioReviewView.tsx
│   │   │   ├── ScenarioEditView.tsx   # TTS trigger + audio/slideshow
│   │   │   └── FinalValidationView.tsx
│   │   ├── components/
│   │   └── hooks/useSessionStore.ts
│   └── package.json
├── src/
│   ├── server/                    # FastAPI backend
│   │   ├── app.py                 # Entry point, all routes, TTS + background mix
│   │   ├── automation.py          # Step automations (placeholder for TTS in steps)
│   │   ├── session_store.py       # Session JSON persistence (scenario_audio, etc.)
│   │   ├── chat_agent.py          # WebSocket chat + tool mapping
│   │   └── config.py
│   └── memoiredesterritoires/     # Skills (Python packages)
│       ├── text_to_speech_with_instructions/   # Core TTS skill (Qwen3)
│       │   ├── text_to_speech_with_instructions.py
│       │   └── SKILL.md
│       ├── scenario_maker/        # Wraps orchestrator (Agents 0→3)
│       ├── project_config.py      # load/save project config (voice_instructions)
│       ├── transcription/
│       ├── Slideshow/
│       └── ...
├── orchestrator.py                 # ScenarioMakerOrchestrator (Agents 0→3)
├── agents/                        # Agent 1 (structure), Agent 2 (writing), Agent 3 (production)
├── config/
│   ├── default_config.json        # Agent 0 baseline
│   └── step_config.json          # Steps, skills, automations per step
├── data/
│   ├── projects/<name>/          # config.json, audio/, outputs/, slides/, videos/
│   ├── sessions/*.json           # Session state (scenarios, scenario_audio, etc.)
│   ├── audio/background_sounds/
│   └── generated_speech/         # TTS output WAVs (tts_*_timestamp.wav)
├── models/qwen3-tts/             # Optional local Qwen3 TTS weights
├── main.py                        # CLI with skill invocations (including TTS)
└── pyproject.toml                 # qwen-tts>=0.0.5, torch, soundfile, etc.
```

---

## 2. App workflow (six steps)

| Step | ID | Main actions |
|------|----|--------------|
| 1 | `project_selection` | Create/choose project; backend creates `data/projects/<name>/`. |
| 2 | `project_details` | Brief, audience, tone, target duration, **voice instructions**. `advanceStep` → `update_project_notes` + `project_config_builder`. |
| 3 | `audio_sources` | Upload WAV/MP3 (1 voice + up to 2 ambiances). Transcription (OpenRouter), DuckDB, background inventory. |
| 4 | `scenario_review` | `POST /scenarios/generate` → ScenarioMakerSkill (orchestrator Agents 0→3). Rank scenarios; optional **pitch TTS** via chat skill `text_to_speech_with_instructions`. Select one scenario. |
| 5 | `scenario_edit` | Edit title/parts; **Regenerate audio** → `POST /sessions/{id}/scenario-audio` (full TTS pipeline). Upload images; create slideshow (MoviePy). |
| 6 | `final_validation` | Persist final assets to `outputs/`; set `final_scenario`, `final_audio`, `final_slideshow`. |

Step config is in **`config/step_config.json`**: each step has `skills` and `automations`. TTS is available as a **skill** in `scenario_review` and `scenario_edit` (chat can call `text_to_speech_with_instructions`). The **main user-facing TTS** is the “Regenerate audio” button on the Edit step, which calls the **scenario-audio API** (see below).

---

## 3. TTS process (detailed)

### 3.1 Where TTS is used

- **Primary path (UI):** “Modifier le scénario” (Scenario Edit) → button “Régénérer l’audio” → `POST /sessions/{session_id}/scenario-audio` → full synthesis + background mix → session and project get the new audio path.
- **Chat path:** In steps 4 and 5, the chat agent can call the skill `text_to_speech_with_instructions` (e.g. to generate a short pitch). Same underlying function, different entry (tool call from chat).
- **CLI:** `main.py` can invoke the same skill by name.

### 3.2 Backend flow (scenario-audio)

1. **Route:** `POST /sessions/{session_id}/scenario-audio` in `src/server/app.py` (`synthesize_scenario_audio`).
2. **Input:** Session + optional body `{ "text": "...", "language": "French" }`. If `text` is omitted, text is derived from the **selected scenario** via `scenario_to_text()` (concatenates `parties[].texte_narration` or `texte` / `resume`).
3. **Voice instructions:**  
   - Project’s `voice_instructions` are read from `data/projects/<name>/config.json`.  
   - If the TTS skill raises (e.g. “no voice instructions”), the server calls `ensure_voice_instructions(project_name, scenario_text, language)` to compose or translate a default (from project notes/tone/audience + optional French→English hint), saves to config, then retries synthesis.
4. **Synthesis:**  
   `text_to_speech_with_instructions(text=..., project_name=..., language=...)`  
   → implemented in `src/memoiredesterritoires/text_to_speech_with_instructions/text_to_speech_with_instructions.py`.
5. **Background mix:**  
   `apply_background_selection(voice_path, project_name, scenario_text)`  
   - Loads audio selection (voices + backgrounds) for the project.  
   - Builds a **background plan** (LLM or fallback): segments of 5–10 s, non-overlapping, for the narration duration.  
   - Overlays selected background files at planned times with attenuation (~-16.48 dB).  
   - Replaces the voice file with the mixed result; keeps a `_dry` copy for `voice_only_path`.
6. **Session storage:**  
   `session_store.save_scenario_audio(session_id, metadata)` with `path`, `generated_at`, `backgrounds_applied`, `background_plan`, `voice_only_path`, etc.
7. **Response:** Metadata (path, duration, language, backgrounds_applied, …).  
   **Streaming file:** `GET /sessions/{session_id}/scenario-audio/file` → `FileResponse` of the WAV.

### 3.3 TTS skill implementation (`text_to_speech_with_instructions`)

- **File:** `src/memoiredesterritoires/text_to_speech_with_instructions/text_to_speech_with_instructions.py`.
- **Dependencies:** `qwen_tts` (`Qwen3TTSModel`), `torch`, `soundfile`. Model: `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` or local `models/qwen3-tts` (env `QWEN_TTS_LOCAL_DIR`).
- **Voice instructions:** Read from project config (`load_project_config(project_name)`) → `voice_instructions`. If missing/empty, raises `ValueError` (server then runs `ensure_voice_instructions` and retries).
- **Output:** WAV in `data/generated_speech/tts_{safe_snippet}_{timestamp}.wav`. Filename snippet is a sanitized prefix of the voice instructions (e.g. `tts_use-a-female-voice-pedagogical_20260220T114634Z.wav`).
- **Return:** `{ "status", "path", "language", "sample_rate", "num_samples", "project", "instructions" }`.
- **Device/dtype:** CUDA (float16) or MPS (float32 to avoid NaNs) or CPU (float32). Model is cached per `(model_source, device, dtype)`.

### 3.4 Frontend (Scenario Edit)

- **Queries:**  
  - `fetchScenarioAudio(sessionId)` → `GET /sessions/{id}/scenario-audio` (metadata).  
  - Audio URL: `getScenarioAudioUrl(sessionId)` → `/sessions/{id}/scenario-audio/file` (optional cache-bust with `generated_at`).
- **Regenerate:**  
  `regenerateAudio()` → `persistScenario()` then `synthesizeScenarioAudio(sessionId)` → `POST /sessions/{id}/scenario-audio`, then `audioQuery.refetch()`.
- **Validation:** Before advancing to “Validation finale”, the UI expects existing audio (`audioQuery.data?.path`); otherwise it asks the user to generate it first.

### 3.5 Data flow summary

```
Project config (voice_instructions, audience, tone)
       ↓
POST /sessions/{id}/scenario-audio
       ↓
scenario_to_text(selected_scenario)  [if no text in body]
       ↓
ensure_voice_instructions()  [if TTS raises "no voice"]
       ↓
text_to_speech_with_instructions(text, project_name, language)
  → load_project_config → voice_instructions
  → Qwen3TTSModel.generate_voice_design(text, language, instruct=...)
  → sf.write(output_path)
       ↓
apply_background_selection(voice_path, project_name, scenario_text)
  → plan_background_segments (LLM or fallback)
  → overlay segments (pydub), save mixed file, keep _dry
       ↓
session_store.save_scenario_audio(session_id, metadata)
       ↓
GET .../scenario-audio/file → stream WAV
```

---

## 4. Key files reference

| Concern | File(s) |
|--------|--------|
| TTS entry (API) | `src/server/app.py` → `synthesize_scenario_audio`, `ensure_voice_instructions`, `apply_background_selection` |
| TTS implementation | `src/memoiredesterritoires/text_to_speech_with_instructions/text_to_speech_with_instructions.py` |
| Voice instructions | `src/server/app.py` (`ensure_voice_instructions`, `_compose_voice_instructions`, `_maybe_translate_voice_hint`); `data/projects/<name>/config.json` → `voice_instructions` |
| Session audio storage | `src/server/session_store.py` → `save_scenario_audio`, `get_scenario_audio` |
| Scenario → text | `src/server/app.py` → `scenario_to_text`, `extract_scenario_payload` |
| Frontend TTS trigger | `app/src/views/ScenarioEditView.tsx` → `regenerateAudio`, `synthesizeScenarioAudio`, `audioQuery` |
| API client | `app/src/api/client.ts` → `fetchScenarioAudio`, `synthesizeScenarioAudio`, `getScenarioAudioUrl` |
| Steps & skills | `config/step_config.json`; `src/server/automation.py` (TTS listed as automation name but handled as placeholder; real call is via API or chat tool) |
| Scenario generation | `src/memoiredesterritoires/scenario_maker/scenario_maker.py` → `ScenarioMakerSkill`; `orchestrator.py` → `ScenarioMakerOrchestrator` (Agents 0→3) |

---

## 5. Logs and debugging

- **TTS start:** `SCENARIO_AUDIO_START` (session, project, language).
- **TTS success:** `SCENARIO_AUDIO_DONE` (path, num_samples); `SCENARIO_AUDIO_BACKGROUND_APPLIED` when backgrounds are mixed.
- **Voice instructions missing:** Server logs “Voice instructions missing for … – composing default” and calls `ensure_voice_instructions` before retry.
- **Recent logs:** `GET /logs/recent?lines=100` (reads `LOG_FILE`, default `./logs/memoire_territoires.log`).

This overview should be enough to navigate the repo and trace any issue from UI → API → TTS skill → Qwen3 → background mix → session/store.
