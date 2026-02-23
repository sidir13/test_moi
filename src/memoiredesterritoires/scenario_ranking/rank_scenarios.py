"""Rank scenarios against a config using an LLM and persist the order."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
import unicodedata
from typing import Any, Dict, List, Optional, Set, Union

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


def _scenario_summary(source: Union[Path, Dict[str, Any]]) -> str:
    if isinstance(source, Path):
        data = _load_json(source)
    else:
        data = source
    snippets = _flatten_texts(data)
    if snippets:
        return "\n".join(snippets)[:1500]
    return json.dumps(data, ensure_ascii=False)[:1500]


def _normalize_label(label: Any) -> str:
    if label is None:
        return ""
    text = str(label).strip()
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.replace("’", "'").lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return normalized.strip()


def _build_aliases(file_name: str, data: Dict[str, Any]) -> Set[str]:
    aliases = {
        file_name,
        Path(file_name).name,
        Path(file_name).stem,
    }
    scenario_id = data.get("scenario_id")
    if scenario_id is not None:
        scenario_id_str = str(scenario_id)
        aliases.update(
            {
                scenario_id_str,
                f"scenario {scenario_id_str}",
                f"scenario_{scenario_id_str}",
                f"scénario {scenario_id_str}",
            }
        )
    for key in ("titre", "title", "titre_global", "scenario_title"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            aliases.add(value)
    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        for key in ("titre", "titre_global", "title"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                aliases.add(value)

    normalized_aliases: Set[str] = set()
    for alias in aliases:
        normalized = _normalize_label(alias)
        if normalized:
            normalized_aliases.add(normalized)
    return normalized_aliases


def _match_candidate(candidate: str, scenario_infos: List[Dict[str, Any]]) -> Optional[str]:
    if not candidate:
        return None

    attempts = [candidate]
    stripped_prefix = re.sub(r"^[\s\-\d\.\)\(]+", "", candidate)
    if stripped_prefix != candidate:
        attempts.append(stripped_prefix)
    dash_split = re.split(r"[–—\-:]+", candidate, 1)
    if len(dash_split) == 2 and dash_split[1].strip():
        attempts.append(dash_split[1])

    seen_attempts: Set[str] = set()
    for attempt in attempts:
        if attempt in seen_attempts:
            continue
        seen_attempts.add(attempt)
        normalized = _normalize_label(attempt)
        if not normalized:
            continue

        for info in scenario_infos:
            if normalized in info["aliases"]:
                return info["name"]

        for info in scenario_infos:
            for alias in info["aliases"]:
                if len(alias) <= 1:
                    continue
                if alias in normalized:
                    return info["name"]
    return None


def _complete_ranking(selected: List[str], scenario_infos: List[Dict[str, Any]]) -> List[str]:
    ordered: List[str] = []
    for name in selected:
        if name and name not in ordered:
            ordered.append(name)
    for info in scenario_infos:
        if info["name"] not in ordered:
            ordered.append(info["name"])
    return ordered


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


def _parse_ranking(response: str, scenario_infos: List[Dict[str, Any]]) -> List[str]:
    response = response.strip()
    try:
        data = json.loads(response)
        if isinstance(data, list):
            matches = []
            for item in data:
                name = _match_candidate(str(item), scenario_infos)
                if name:
                    matches.append(name)
            if matches:
                return _complete_ranking(matches, scenario_infos)
        if isinstance(data, dict):
            for key in ("ranking", "order", "scenarios", "result"):
                value = data.get(key)
                if isinstance(value, list):
                    matches = []
                    for item in value:
                        name = _match_candidate(str(item), scenario_infos)
                        if name:
                            matches.append(name)
                    if matches:
                        return _complete_ranking(matches, scenario_infos)
            if all(isinstance(value, str) for value in data.values()):
                matches = []
                for value in data.values():
                    name = _match_candidate(value, scenario_infos)
                    if name:
                        matches.append(name)
                if matches:
                    return _complete_ranking(matches, scenario_infos)
    except json.JSONDecodeError:
        pass

    names = []
    for line in response.splitlines():
        cleaned = line.strip().strip("[]\"'")
        if not cleaned:
            continue
        parts = re.split(r"[,;]", cleaned) if "," in cleaned or ";" in cleaned else [cleaned]
        for part in parts:
            candidate = re.sub(r"^[\d]+\s*[\).\-\]]*\s*", "", part).strip()
            name = _match_candidate(candidate, scenario_infos)
            if name and name not in names:
                names.append(name)
    if names:
        return _complete_ranking(names, scenario_infos)

    return [info["name"] for info in scenario_infos]


def _readable_value(value: Optional[str]) -> str:
    if not value:
        return ""
    return value.replace("_", " ").replace("-", " ").strip()


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

    scenario_infos: List[Dict[str, Any]] = []
    for file in scenario_files:
        payload = _load_json(file)
        scenario_infos.append({
            "name": file.name,
            "summary": _scenario_summary(payload),
            "aliases": _build_aliases(file.name, payload),
        })

    gen_params = (
        config.get("scenario_config", {})
        .get("generation_parameters", {})
        if isinstance(config.get("scenario_config"), dict)
        else {}
    )
    tone_value = _readable_value(
        (gen_params or {}).get("ton", {}).get("value")
        if isinstance(gen_params, dict)
        else None
    )
    audience_value = _readable_value(
        (gen_params or {}).get("public_cible", {}).get("value")
        if isinstance(gen_params, dict)
        else None
    )
    duration_value = (
        (gen_params or {}).get("duree", {}).get("value")
        if isinstance(gen_params, dict)
        else None
    )

    constraint_lines: List[str] = []
    if tone_value or audience_value or duration_value:
        constraint_lines.append(
            "IMPORTANT : pénalise immédiatement tout scénario qui ne respecte pas les paramètres suivants."
        )
        if audience_value:
            constraint_lines.append(
                f"- Public cible imposé : {audience_value}. Le texte doit être adapté à ce public et le signaler clairement dès l'introduction."
            )
        if tone_value:
            constraint_lines.append(
                f"- Ton narratif imposé : {tone_value}. Aucune digression vers un autre ton n'est acceptée."
            )
        if duration_value:
            constraint_lines.append(
                f"- Durée attendue : ~{duration_value} secondes (tolérance maximale ±15 %)."
            )
        constraint_lines.append(
            "- Les scénarios doivent rappeler dans les premières phrases le public et le ton imposés."
        )
        constraint_lines.append(
            "- Classe d'abord sur la conformité, ensuite sur la cohérence historique et l'impact narratif."
        )

    prompt_lines = [
        "Tu dois classer les scénarios du meilleur au moins adapté selon le cahier des charges suivant.",
        "Renvoie STRICTEMENT une liste JSON ordonnée des noms de fichiers.",
        "",
        "Cahier des charges:",
        config_str,
    ]
    if constraint_lines:
        prompt_lines.append("")
        prompt_lines.extend(constraint_lines)
    prompt_lines.extend([
        "",
        "Scénarios:",
    ])
    for info in scenario_infos:
        prompt_lines.append(f"- {info['name']}: {info['summary']}")

    prompt = "\n".join(prompt_lines)
    raw = _call_llm(prompt)
    ranking = _parse_ranking(raw, scenario_infos)

    config.setdefault("scenario_config", {})["scenario_ranking"] = ranking
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    return {
        "status": "ranked",
        "project_name": project_name,
        "config_path": str(config_file),
        "ranking": ranking,
    }
