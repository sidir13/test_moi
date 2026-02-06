# Mémoire des Territoires – Skill Documentation

This agent exposes a set of tools (“skills”) that orchestrate audio processing, archival research, and scenario building tasks. Each skill is driven by a dedicated Python module under `src/memoiredesterritoires/...` and described via a `SKILL.md`. Use the catalog below to understand when and how each tool should be triggered.

| Skill | Purpose | Typical Inputs | Notes / Module |
| --- | --- | --- | --- |
| `process-number` | Toy example that doubles an integer. | `num` (int) | `src/memoiredesterritoires/process_number/process_number.py` |
| `phone_number` | Format/analyse French 04/06 numbers with cultural hints. | `number` (string) | `src/memoiredesterritoires/phone_number/SKILL.md` |
| `signature` | Enforce a `yipikayak !` signature at the end of replies. | (none) | `src/memoiredesterritoires/signature/SKILL.md` |
| `adjust-audio-volume` | Apply logarithmic gain to an audio file and report RMS/gain changes. | `input_file` (required), `output_file`, `volume_percent` | `src/memoiredesterritoires/adjust_audio_volume/adjust_audio_volume.py` |
| `transcribe_audio` | Chunk a WAV, send each slice to Gemini via OpenRouter, and rebuild the full transcription with timestamps. | `path` (required), optional `chunk_duration_s`, `model` | `src/memoiredesterritoires/transcription/transcription.py` |
| `background_sounds_description` | Analyse an industrial ambience (tool identification, context summary). | `path`, optional `context` | `src/memoiredesterritoires/background_sounds_description/background_sounds_description.py` |
| `mix_voice_with_noise` | Overlay a background ambience on a narration while targeting a specific SNR and duration. | `voice_file`, `noise_file`, optional `snr_db`, `start_time`, `noise_duration`, `noise_start_offset`, `output_file` | `src/memoiredesterritoires/insert_background_sounds/insert_backgrounds_sounds.py` |
| `find-background-sounds` | List available files under `data/audio/background_sounds`, optionally filtered by keyword. | `keyword`, `limit` | `src/memoiredesterritoires/background_sound_finder/background_sound_finder.py` |
| `save-audio-analysis` | Persist transcription / background analyses into the Parquet dataset (`data/audio_analysis/audio_analysis.parquet`). | `analysis_type`, `source_path`, `title`, `result`, optional metadata/tags/context | `src/memoiredesterritoires/analysis_storage/analysis_storage.py` |
| `list-audio-analyses` | Query previous analysis entries (filter by type/path substring). | `analysis_type`, `source_path_contains`, `limit` | `src/memoiredesterritoires/analysis_storage_query/SKILL.md` |
| `text-to-speech-with-instructions` | Generate speech with the Qwen 1.7B VoiceDesign model using the voice instructions stored in `config.json`. | `text`, optional `project_name`, `language`, `output_path` | `src/memoiredesterritoires/text_to_speech_with_instructions/text_to_speech_with_instructions.py` |
| `edit_voice_instructions` | Update the `voice_instructions` block for a project (must translate the user request into English). | `project_name`, `voice_instructions` | `src/memoiredesterritoires/voice_instructions/edit_voice_instructions.py` |
| `generate-voice-instructions` | Ask the LLM to craft new voice instructions from a historical scenario and persist them. | `scenario` (text), optional `project_name`, `hint_language` | `src/memoiredesterritoires/voice_instructions/generate_voice_instructions.py` |
| `restricted-web-search` | Perform an OpenRouter web search restricted to the `allowed_websites` configured for the project. | `query`, optional `project_name`, `max_results`, `model` | `src/memoiredesterritoires/web_search/restricted_web_search.py` |
| `eleven_labs_tts` | Produce an MP3 narration with the ElevenLabs API when explicitly requested. | `text`, optional `voice_id`, `model_id`, `output_path` | `src/memoiredesterritoires/elevenlabs_tts/elevenlabs_tts.py` |
| `read_json_file` | Load a local JSON file (optionally scoped to a `project_name` and/or key). | `path`, optional `project_name`, `key` | `src/memoiredesterritoires/json_utils/read_json.py` |
| `rank_scenarios_against_config` | Ask the LLM to compare each scenario against a project config, produce an ordered list, and persist it under `scenario_ranking`. | `config_path`, `scenarios_dir`, optional `project_name` | `src/memoiredesterritoires/scenario_ranking/rank_scenarios.py` |
| `update_project_notes` | Store free-form user briefs/requirements for a project in `config.json` so other skills can reuse them. | `description`, optional `project_name` | `src/memoiredesterritoires/project_notes/update_project_notes.py` |

### Usage Guidelines
1. **Skill Context:** `main.py` stitches the content of every `SKILL*.md` into the system prompt. Update SKILL docs whenever inputs/behavior change so Claude can self-select the right tool.
2. **Project-aware Controls:** Some skills (e.g., `restricted-web-search`, `generate-voice-instructions`, TTS) read project metadata from `config.json`. Ensure the desired project has the necessary fields (`allowed_websites`, `voice_instructions`) before invoking them.
3. **Persistence:** Analysis results are stored as Parquet via DuckDB. Use `save-audio-analysis` immediately after finishing a transcription or ambience description, then `list-audio-analyses` to audit what was stored.
4. **Audio Assets:** `data/audio/background_sounds/` is the canonical source for ambient noises. Use `find-background-sounds` to discover valid paths before calling `mix_voice_with_noise`.

Extend this table whenever you add a new `SKILL.md` so the README remains the single source of truth for tool capabilities.
