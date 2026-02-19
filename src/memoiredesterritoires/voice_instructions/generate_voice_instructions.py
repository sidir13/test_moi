"""Generate scenario-based voice instructions and persist them in the project config."""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from memoiredesterritoires.project_config import (
    DEFAULT_PROJECT_NAME,
    load_project_config,
    save_project_config,
)

DEFAULT_PROJECT = DEFAULT_PROJECT_NAME


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

    entry = load_project_config(project)
    entry["voice_instructions"] = voice_instructions
    entry["voice_instructions_source"] = "llm"
    config_path = save_project_config(project, entry)

    return {
        "status": "generated",
        "project": project,
        "voice_instructions": voice_instructions,
        "config_path": str(config_path),
    }
