"""Generate scenario-based voice instructions and persist them in config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_PROJECT = "Mémoire des Territoires"
CONFIG_PATH = Path(__file__).resolve().parents[3] / "config.json"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _call_llm(prompt: str) -> str:
    load_dotenv()
    client = OpenAI(
        base_url=os.getenv("ANTHROPIC_BASE_URL"),
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
    )
    completion = client.chat.completions.create(
        model="google/gemini-3-flash-preview",
        messages=[
            {"role": "system", "content": "Tu rédiges des consignes vocales en anglais."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=200,
    )
    if isinstance(completion, str):
        return completion.strip()
    content = completion.choices[0].message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
        return text.strip()
    return str(content).strip()


def generate_voice_instructions(
    scenario: str,
    project_name: Optional[str] = None,
    hint_language: str = "French",
) -> dict:
    if not scenario or not scenario.strip():
        raise ValueError("scenario must be provided")

    project = project_name.strip() if project_name else DEFAULT_PROJECT

    prompt = (
        "Voici un scénario audio. Crée des instructions de voix en anglais, adaptées à l'époque et au ton,"
        " en indiquant timbre, âge, énergie, respiration, diction.\n"
        f"Scénario (langue={hint_language}):\n{scenario.strip()}"
    )

    voice_instructions = _call_llm(prompt)

    config = _load_config()
    entry = config.setdefault(project, {})
    entry["voice_instructions"] = voice_instructions
    entry["voice_instructions_source"] = "llm"
    _save_config(config)

    return {
        "status": "generated",
        "project": project,
        "voice_instructions": voice_instructions,
        "config_path": str(CONFIG_PATH),
    }
