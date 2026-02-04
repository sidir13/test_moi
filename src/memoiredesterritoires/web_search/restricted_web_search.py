"""
Project-aware web search helper that limits sources to approved domains.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_PROJECT = "Mémoire des Territoires"
CONFIG_PATH = Path(__file__).resolve().parents[3] / "config.json"


def _load_allowed_websites(project_name: Optional[str]) -> List[str]:
    project = project_name.strip() if project_name else DEFAULT_PROJECT
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"config.json not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    entry = config.get(project)
    if not entry:
        raise KeyError(f"Project '{project}' not found in config.json")
    allowed = entry.get("allowed_websites")
    if not allowed:
        raise ValueError(f"No allowed_websites configured for project '{project}'")
    return project, allowed


def restricted_web_search(
    query: str,
    project_name: Optional[str] = None,
    *,
    model: str = "google/gemini-3-pro-preview",
    max_results: int = 5,
    env_var_base_url: str = "ANTHROPIC_BASE_URL",
    env_var_api_key: str = "ANTHROPIC_AUTH_TOKEN",
) -> Dict[str, Any]:
    """
    Run a web-enabled OpenRouter call constrained to the project's allowed websites.
    """
    if not query or not query.strip():
        raise ValueError("query must be provided")

    project, allowed_sites = _load_allowed_websites(project_name)

    load_dotenv()
    raw_base_url = os.getenv(env_var_base_url)
    api_key = os.getenv(env_var_api_key)
    if not raw_base_url or not api_key:
        raise EnvironmentError("Missing OpenRouter base URL or API key in environment")

    base_url = raw_base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    client = OpenAI(base_url=base_url, api_key=api_key)

    system_prompt = (
        "Tu es un chercheur spécialisé dans les archives industrielles françaises. "
        "Tu dois STRICTEMENT t'appuyer sur les sources provenant des domaines suivants : "
        f"{', '.join(allowed_sites)}. "
        "Ignore toute autre source, même si elle apparaît dans les résultats."
    )

    search_prompt = (
        "Récolte uniquement des informations provenant des domaines autorisés : "
        f"{', '.join(allowed_sites)}. "
        "Ignore ou rejette toute autre page proposée."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query.strip()},
    ]

    model_name = model
    if not model_name.endswith(":online"):
        model_name = f"{model_name}:online"

    completion = client.chat.completions.create(
        model=model_name,
        messages=messages,
        extra_body={
            "plugins": [
                {
                    "id": "web",
                    "max_results": max_results,
                    "search_prompt": search_prompt,
                }
            ]
        },
    )

    def _coerce_content(result: Any) -> str:
        if isinstance(result, str):
            return result
        if hasattr(result, "choices"):
            message = result.choices[0].message
            content = message.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                pieces = []
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        pieces.append(block["text"])
                    elif isinstance(block, str):
                        pieces.append(block)
                return "\n".join(pieces)
        return json.dumps(result, ensure_ascii=False)

    content = _coerce_content(completion)
    return {
        "project": project,
        "allowed_websites": allowed_sites,
        "model": model_name,
        "query": query,
        "response": content,
    }
