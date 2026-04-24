# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend
```bash
# Dev server (hot-reload)
uv run uvicorn server.app:create_app --factory --reload

# Install Python deps only
uv sync
```

### Frontend
```bash
cd app && npm run dev         # http://localhost:5173
cd app && npm run build       # production build (required before make run-app)
```

### Full stack (prod-like)
```bash
make install PLATFORM=mac     # uv sync + npm install + npm build + download Qwen model
make run-app                  # uv sync + npm install + npm build + uvicorn
```

### Tests
```bash
uv run pytest                           # all tests
uv run pytest tests/test_agent_0.py -v # single file
uv run pytest -m "not slow" -v          # skip slow tests
```

### Docker
```bash
make docker-build PLATFORM=mac
make docker-run PLATFORM=mac
make docker-refresh-mac                 # rebuild + run shortcut
```

## Architecture

### Three-layer system

```
Frontend (React/Vite)  ──HTTP/WS──▶  Backend (FastAPI)  ──▶  Agent pipeline / Skills
app/src/                             src/server/app.py         agents/ + src/memoiredesterritoires/
```

### Backend entry point

`src/server/app.py` — single FastAPI application (`create_app` factory). Mounts:
- REST routes for projects, sessions, audio, scenarios, TTS, slideshow
- `GET /ws/chat?session_id=...` WebSocket for the LLM copilot (`src/server/chat_agent.py`)

`src/server/chat_agent.py` proxies Anthropic Claude calls and maps `tool_use` blocks to Python skill functions from `src/memoiredesterritoires/`.

`src/server/automation.py` runs automation chains when a session advances a step (`POST /sessions/{id}/step`). Which automations fire per step is declared in `config/step_config.json`.

### 4-agent scenario pipeline

Lives in `orchestrator.py` (`ScenarioMakerOrchestrator`) and is triggered by `src/memoiredesterritoires/scenario_maker/`. Executes:

```
Agent 0 (parser.py) — Claude Sonnet, temp 0.1
  → produces N scenarioPrompts

[parallel via ThreadPoolExecutor]
  Agent 1 (structure.py) — Claude Sonnet, temp 0.7
  → Agent 2 (writer.py)  — Claude Opus,   temp 0.8
  → Agent 3 (production.py) — Claude Sonnet, temp 0.3  [only when tts_provider=elevenlabs]
```

Agents live in `agents/<agent_name>/` (Python class + `skill.md` describing the LLM task). Dynamically loaded by `utils/skill_loader.py` (`SkillLoader`).

### Skills catalogue

Every skill is a folder under `src/memoiredesterritoires/<skill_name>/` with:
- A Python module implementing the tool function
- A `SKILL.md` describing its interface (used by the chat agent as tool documentation)

The chat copilot exposes only skills listed in the current step's `"skills"` array in `config/step_config.json`.

### Data layout

```
data/projects/<name>/
  config.json          ← consolidated project state (notes, ton, public, voice_instructions,
                          scenarios, rankings, final asset paths)
  audio/               ← uploaded voice/ambiance files
  outputs/             ← audio_<slug>.wav, video_<slug>.mp4 (finalized)

data/sessions/*.json   ← per-session snapshots + skill call log (can be cleaned)
data/audio/background_sounds/ ← shared library of ambiances
```

### Frontend state

`app/src/hooks/useSessionStore.ts` — Zustand store holding session, project, current step, language, and `progress` flags (`audioReady`, `transcriptionsReviewed`, `scenariosReady`, `scenarioChosen`, `scenarioEdited`). These flags gate navigation between the 7 steps defined in `config/step_config.json`.

Views map 1-to-1 to steps: `app/src/views/` has `ProjectSelectionView`, `ProjectDetailsView`, `AudioSelectionView`, `TranscriptionReviewView`, `ScenarioReviewView`, `ScenarioEditView`, `FinalValidationView`.

### API / model wiring

`utils/claude_client.py` wraps the Anthropic SDK. It reads `ANTHROPIC_AUTH_TOKEN` and optionally `ANTHROPIC_BASE_URL` (set to OpenRouter for model routing). Agent model strings in `agents/*/skill.md` use `anthropic/claude-*` format (OpenRouter convention).

The `config/model_registry.py` and `config/default_config.json` together define the baseline generation parameters (tone options, audience types, durations, etc.) that Agent 0 merges with user input.

## Required environment variables

```
ANTHROPIC_AUTH_TOKEN   # Anthropic key (or OpenRouter key when using ANTHROPIC_BASE_URL)
ANTHROPIC_BASE_URL     # e.g. https://openrouter.ai/api/v1
OPENROUTER_API_KEY     # for transcription via OpenRouter
ELEVENLABS_API_KEY     # optional, if using ElevenLabs TTS
VITE_API_BASE          # http://localhost:8000 in dev (consumed by Vite proxy)
MAX_AUDIO_MB           # upload limit, default 500
BACKGROUND_PLAN_MODEL  # model for background sound planner
VOICE_TRANSLATION_MODEL # model for voice instruction translation
SCENARIO_DEFAULT_CONFIG # optional path to override the default config for Agent 0
```

Copy `env.example` → `.env` and fill in before running anything.
