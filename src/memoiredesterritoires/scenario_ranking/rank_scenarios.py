"""Rank scenarios against a config using an LLM and persist the order."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, List, Optional

from dotenv import load_dotenv
from openai import OpenAI


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _flatten_texts(data) -> List[str]:
    texts: List[str] = []

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                texts.extend(_flatten_texts(value))
            elif isinstance(value, str) and re.search(r"texte|narration|content", key, re.IGNORECASE):
                texts.append(value)
    elif isinstance(data, list):
        for item in data:
            texts.extend(_flatten_texts(item))

    return texts


def _scenario_summary(path: Path) -> str:
    data = _load_json(path)
    snippets = _flatten_texts(data)
    if snippets:
        return "\n".join(snippets)[:1500]
    return json.dumps(data, ensure_ascii=False)[:1500]


def _normalize_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    if content is None:
        return ""
    return str(content)


def _extract_completion_text(completion: Any) -> str:
    if completion is None:
        return ""

    if hasattr(completion, "choices"):
        choices = getattr(completion, "choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            if message and hasattr(message, "content"):
                return _normalize_message_content(message.content)
            if isinstance(first_choice, dict):
                message_dict = first_choice.get("message")
                if isinstance(message_dict, dict) and "content" in message_dict:
                    return _normalize_message_content(message_dict["content"])
                if "content" in first_choice:
                    return _normalize_message_content(first_choice["content"])

    if isinstance(completion, dict):
        if "choices" in completion:
            return _extract_completion_text(completion["choices"])
        if "message" in completion and isinstance(completion["message"], dict):
            content = completion["message"].get("content")
            if content is not None:
                return _normalize_message_content(content)
        if "content" in completion:
            return _normalize_message_content(completion["content"])

    if isinstance(completion, list) and completion:
        first_item = completion[0]
        if isinstance(first_item, dict):
            message = first_item.get("message")
            if isinstance(message, dict) and "content" in message:
                return _normalize_message_content(message["content"])
            if "content" in first_item:
                return _normalize_message_content(first_item["content"])
        if hasattr(first_item, "message") and hasattr(first_item.message, "content"):
            return _normalize_message_content(first_item.message.content)

    if isinstance(completion, str):
        try:
            data = json.loads(completion)
        except json.JSONDecodeError:
            return completion
        return _extract_completion_text(data)

    return _normalize_message_content(completion)


def _call_llm(prompt: str) -> str:
    load_dotenv()
    client = OpenAI(
        base_url=os.getenv("ANTHROPIC_BASE_URL"),
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
    )
    completion = client.chat.completions.create(
        model="google/gemini-3-flash-preview",
        messages=[
            {"role": "system", "content": "Tu es un évaluateur qui classe les scénarios selon les instructions données."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=600,
    )
    return _extract_completion_text(completion)


def _parse_ranking(response: str, scenario_names: List[str]) -> List[str]:
    response = response.strip()
    try:
        data = json.loads(response)
        if isinstance(data, list):
            cleaned = [str(item) for item in data if str(item) in scenario_names]
            if cleaned:
                return cleaned
    except json.JSONDecodeError:
        pass

    names = []
    for line in response.splitlines():
        line = line.strip(" -.")
        for name in scenario_names:
            if name in line and name not in names:
                names.append(name)
    return names or scenario_names


def rank_scenarios_against_config(
    config_path: str,
    scenarios_dir: str,
    project_name: Optional[str] = None,
) -> dict:
    config_file = Path(config_path)
    config = _load_json(config_file)
    config_str = json.dumps(config, ensure_ascii=False)[:4000]

    scenarios_path = Path(scenarios_dir)
    scenario_files = sorted(
        [p for p in scenarios_path.glob("*.json") if "config" not in p.name.lower()]
    )
    if not scenario_files:
        raise FileNotFoundError(f"Aucun scénario trouvé dans {scenarios_path}")

    scenario_infos = []
    for file in scenario_files:
        scenario_infos.append({
            "name": file.name,
            "summary": _scenario_summary(file),
        })

    prompt_lines = [
        "Tu dois classer les scénarios du meilleur au moins adapté selon le cahier des charges suivant.",
        "Renvoie STRICTEMENT une liste JSON ordonnée des noms de fichiers.",
        "",
        "Cahier des charges:",
        config_str,
        "",
        "Scénarios:",
    ]
    for info in scenario_infos:
        prompt_lines.append(f"- {info['name']}: {info['summary']}")

    prompt = "\n".join(prompt_lines)
    raw = _call_llm(prompt)
    scenario_names = [info["name"] for info in scenario_infos]
    ranking = _parse_ranking(raw, scenario_names)

    config.setdefault("scenario_config", {})["scenario_ranking"] = ranking
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    return {
        "status": "ranked",
        "project_name": project_name,
        "config_path": str(config_file),
        "ranking": ranking,
    }
