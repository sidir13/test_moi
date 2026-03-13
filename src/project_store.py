"""Shared helpers for project-level metadata (scenario targets, audio selection)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

BASE_PROJECTS_DIR = Path(os.getenv("PROJECTS_DIR", "data/projects"))
BACKGROUND_DIR = Path("data/audio/background_sounds")


def _project_dir(name: str) -> Path:
    path = BASE_PROJECTS_DIR / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_project_settings(project_name: str) -> Dict[str, int]:
    path = _project_dir(project_name) / "settings.json"
    if not path.exists():
        return {"scenario_target": 3}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("scenario_target", 3)
    return data


def save_project_settings(project_name: str, settings: Dict[str, int]) -> None:
    path = _project_dir(project_name) / "settings.json"
    payload = {"scenario_target": settings.get("scenario_target", 3)}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _normalize_background_selection(raw: Any) -> Dict[str, Any]:
    ambient = None
    punctual: List[str] = []
    if isinstance(raw, dict):
        ambient = raw.get("ambient")
        punctual = raw.get("punctual") or []
    elif isinstance(raw, list):
        punctual = raw
    return {
        "ambient": ambient if isinstance(ambient, str) and ambient.strip() else None,
        "punctual": [p for p in punctual if isinstance(p, str)][:2],
    }


def load_audio_selection(project_name: str) -> Dict[str, Any]:
    path = _project_dir(project_name) / "audio_selection.json"
    if not path.exists():
        return {
            "voices": [],
            "backgrounds": {"ambient": None, "punctual": []},
            "auto_backgrounds": False,
            "tts_voice_id": None,
        }
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    voices = data.get("voices", [])
    backgrounds = _normalize_background_selection(data.get("backgrounds"))
    return {
        "voices": voices if isinstance(voices, list) else [],
        "backgrounds": backgrounds,
        "auto_backgrounds": bool(data.get("auto_backgrounds", False)),
        "tts_voice_id": data.get("tts_voice_id"),
    }


def save_audio_selection(project_name: str, selection: Dict[str, Any]) -> Dict[str, Any]:
    backgrounds = _normalize_background_selection(selection.get("backgrounds"))
    payload = {
        "voices": selection.get("voices", []),
        "backgrounds": backgrounds,
        "auto_backgrounds": bool(selection.get("auto_backgrounds", False)),
        "tts_voice_id": selection.get("tts_voice_id"),
    }
    path = _project_dir(project_name) / "audio_selection.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def list_project_audio_files(project_name: str) -> List[str]:
    audio_dir = _project_dir(project_name) / "audio"
    if not audio_dir.exists():
        return []
    return sorted([f.name for f in audio_dir.iterdir() if f.is_file()])


def get_project_audio_file(project_name: str, file_name: str) -> Path:
    """Return the full path to an audio file within a project."""
    audio_dir = _project_dir(project_name) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir / file_name
