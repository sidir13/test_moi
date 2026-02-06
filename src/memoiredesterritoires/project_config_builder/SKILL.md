---
name: build-project-scenario-config
description: Adapt the default scenario configuration to a specific project by parsing textual instructions and injecting archival resources.
license: MIT
---

# Project Scenario Config Builder Skill

## Mission

Read a narrative brief (plus optional documents and transcripts) and produce a fully-populated `scenario_config` JSON tailored to a new project. The resulting file is meant to be fed into the Scenario Maker skill or the CLI in expert mode before generating narration scenarios.

## Capabilities

- Accept **simple** prompts to auto-extract parameters via Agent 0.
- Merge existing **expert** configurations (dict or JSON path) with the default baseline.
- Inject user-provided **audio_transcriptions** and **documents** into `data_sources.user_provided`.
- Override metadata such as `project_name`.
- Save the adapted config to any desired path (default `output/configs/project_scenario_config.json`).

## Parameters

| Field | Type | Description |
|-------|------|-------------|
| `project_description` | string | Text describing the historical project (required in simple mode). |
| `mode` | `"simple"` or `"expert"` | Simple = parse prompt, Expert = merge provided JSON. |
| `project_config` / `project_config_path` | dict/string | Expert overrides when `mode="expert"`. |
| `base_config_path` | string | Baseline config (default `config/default_config.json`). |
| `output_path` | string | Destination for the generated JSON. |
| `project_name` | string | Updates `metadata.project_name`. |
| `audio_transcriptions` | array | Transcripts `{file_name, transcription, ...}` attached to the config. |
| `documents` | array | Textual documents `{title, content, source}` stored under `user_provided.documents`. |

## Example Usage

```python
skill_input = {
    "project_description": "Documentaire sonore sur les pêcheuses de sardines à Douarnenez dans les années 30",
    "project_name": "Douarnenez 1930",
    "audio_transcriptions": [
        {
            "file_name": "temoignage_marie.wav",
            "transcription": "Je travaillais dès l'aube sur les quais...",
            "language": "fr",
            "source": "Archives familiales"
        }
    ],
    "documents": [
        {
            "title": "Article Ouest-Éclair 1931",
            "content": "L'activité sardinière emploie plus de 300 femmes...",
            "source": "Ouest-Éclair, 12 mai 1931"
        }
    ],
    "output_path": "config/douarnenez_config.json"
}

result = project_config_builder_skill.run(skill_input)
print(result["config_path"])      # config/douarnenez_config.json
```

## Output

Returns `{status, config_path, config}` and writes the JSON file to `output_path`. The `config` can then be passed to `generate_historical_scenario` (Scenario Maker skill) or the CLI (`memoire-territoires generate --mode expert --config ...`).
