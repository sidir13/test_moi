"""Store user descriptions / guidance for a project in config.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

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


def update_project_notes(
    project_name: Optional[str],
    description: str,
) -> dict:
    """Persist a free-form description / requirements block for the project."""

    if not description or not description.strip():
        raise ValueError("description must be provided")

    project = project_name.strip() if project_name else DEFAULT_PROJECT
    config = _load_config()
    entry = config.setdefault(project, {})
    entry["project_notes"] = description.strip()
    _save_config(config)

    return {
        "status": "updated",
        "project": project,
        "project_notes": entry["project_notes"],
        "config_path": str(CONFIG_PATH),
    }
