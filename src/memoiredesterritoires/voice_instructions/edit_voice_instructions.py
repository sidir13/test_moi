"""
Utility to update TTS/STT voice instructions per project.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_PROJECT = "Mémoire des Territoires"
CONFIG_PATH = Path(__file__).resolve().parents[3] / "config.json"


def _load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_config(config: Dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def edit_voice_instructions(project_name: Optional[str], voice_instructions: str) -> Dict[str, Any]:
    """
    Update or create the voice_instructions block for the given project.
    """
    if not voice_instructions or not voice_instructions.strip():
        raise ValueError("voice_instructions must be provided")

    project = project_name.strip() if project_name else DEFAULT_PROJECT
    config = _load_config()
    project_entry = config.setdefault(project, {})
    project_entry["voice_instructions"] = voice_instructions.strip()
    _save_config(config)

    return {
        "status": "updated",
        "project": project,
        "voice_instructions": project_entry["voice_instructions"],
        "config_path": str(CONFIG_PATH),
    }
