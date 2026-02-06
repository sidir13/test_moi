---
name: generate-historical-scenario
description: Launch the Mémoire des Territoires multi-agent pipeline to write historical narration scenarios (JSON) ready for TTS production.
license: MIT
---

# Scenario Maker Skill

## Mission

Transform a project-specific configuration (or the default fallback) plus optional archival transcripts into complete narration scenarios and audio timelines. The generated JSON output follows the structure expected by the Mémoire des Territoires production pipeline and is designed to feed downstream text-to-speech rendering.

## Capabilities

- Accept **simple** mode (natural-language prompt) or **expert** mode (prebuilt configuration JSON).
- Inject user-provided **audio transcriptions** and documents into the pipeline before generation.
- Run the 4-agent architecture (Request Parser → Structure Architect → Scenario Writer → Audio Production) described in `agents.md`.
- Save the resulting **config**, **scenarios**, and **timelines** under the requested output directory (`data/scenarios/...` by default).
- Optionally persist the enriched configuration (`persist_updated_config`, `updated_config_path`) for reproducibility.

## Parameters

| Field | Type | Description |
|-------|------|-------------|
| `prompt` | string | Simple-mode request (e.g., “Souhaite réaliser un scénario orienté sur la pêche côtière à Nantes”). |
| `mode` | `"simple"` or `"expert"` | Simple = parse prompt; Expert = use config JSON. |
| `config_path` | string | Base config file (default `config/default_config.json`). |
| `expert_config` / `expert_config_path` | dict/string | Overrides when `mode="expert"`. |
| `output_dir` | string | Directory for scenario/timeline outputs (default `./output`). |
| `audio_transcriptions` | array | Optional transcripts `{file_name, transcription, ...}` injected into `user_provided`. |
| `persist_updated_config` | boolean | Save the enriched config copy (default `false`). |
| `updated_config_path` | string | Explicit path for the saved config copy. |

## Example Call (pseudo-code)

```python
skill_input = {
    "prompt": "Raconte la vie d'une ouvrière des Conserveries de Douarnenez dans les années 1930",
    "mode": "simple",
    "output_dir": "data/scenarios/douarnenez",
    "audio_transcriptions": [
        {
            "file_name": "temoignage_marie_1932.wav",
            "transcription": "J'avais 16 ans quand j'ai commencé à sertir les boîtes...",
            "language": "fr",
            "source": "Archives familiales"
        }
    ],
    "persist_updated_config": true
}

result = scenario_maker_skill.run(skill_input)
print(result["status"])           # "success"
print(result["skill_metadata"])   # scenario count, output dir, etc.
```

## Output

The skill returns the orchestrator payload:

- `config`: merged configuration JSON.
- `scenarios`: list of `{structure, scenario, timeline}` triples.
- `generation_time`, `status`, `message`.
- `skill_metadata`: `{status, output_dir, config_path, scenario_count}`.

These scenario JSON files (and the matching audio timelines) follow the format illustrated in `agents.md` and are ready for conversion to speech with the existing TTS skills.
