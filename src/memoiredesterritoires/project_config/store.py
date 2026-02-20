"""Shared helpers to persist per-project metadata (voice, notes, outputs, etc.)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

DEFAULT_PROJECT_NAME = os.getenv("DEFAULT_PROJECT_NAME", "Mémoire des Territoires")
_DEFAULT_PROJECTS_DIR = Path(os.getenv("PROJECTS_DIR", "data/projects")).expanduser()
_DEFAULT_CONFIG_FILENAME = os.getenv("PROJECT_CONFIG_FILENAME", "config.json")
_DEFAULT_ROOT_CONFIG = Path(os.getenv("PROJECT_CONFIG_ROOT", "config.json")).expanduser()


def _resolve_projects_dir(projects_dir: Optional[Union[str, Path]]) -> Path:
    if projects_dir is None:
        return _DEFAULT_PROJECTS_DIR
    return Path(projects_dir).expanduser()


def _resolve_filename(filename: Optional[str]) -> str:
    return filename or _DEFAULT_CONFIG_FILENAME


def _resolve_fallback_path(path: Optional[Union[str, Path]]) -> Path:
    if path is None:
        return _DEFAULT_ROOT_CONFIG
    return Path(path).expanduser()


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data
    return {}


def _write_json(path: Path, content: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)


def get_project_config_path(
    project_name: str,
    *,
    projects_dir: Optional[Union[str, Path]] = None,
    filename: Optional[str] = None,
) -> Path:
    if not project_name or not project_name.strip():
        raise ValueError("project_name must be provided")
    project = project_name.strip()
    dir_path = _resolve_projects_dir(projects_dir)
    return (dir_path / project / _resolve_filename(filename)).expanduser()


def load_project_config(
    project_name: str,
    *,
    projects_dir: Optional[Union[str, Path]] = None,
    filename: Optional[str] = None,
    fallback_path: Optional[Union[str, Path]] = None,
    persist_on_fallback: bool = True,
) -> Dict[str, Any]:
    """
    Load the JSON metadata for a project. Falls back to the legacy root config if needed.
    """
    config_path = get_project_config_path(project_name, projects_dir=projects_dir, filename=filename)
    if config_path.exists():
        return _load_json(config_path)

    fallback_file = _resolve_fallback_path(fallback_path)
    if fallback_file.exists():
        legacy = _load_json(fallback_file)
        entry = legacy.get(project_name.strip(), {})
        if isinstance(entry, dict):
            if entry and persist_on_fallback:
                save_project_config(
                    project_name,
                    entry,
                    projects_dir=projects_dir,
                    filename=filename,
                )
            return dict(entry)
    return {}


def save_project_config(
    project_name: str,
    data: Dict[str, Any],
    *,
    projects_dir: Optional[Union[str, Path]] = None,
    filename: Optional[str] = None,
) -> Path:
    if not isinstance(data, dict):
        raise ValueError("data must be a dict")
    config_path = get_project_config_path(project_name, projects_dir=projects_dir, filename=filename)
    _write_json(config_path, data)
    return config_path


def update_project_config(
    project_name: str,
    updates: Dict[str, Any],
    *,
    projects_dir: Optional[Union[str, Path]] = None,
    filename: Optional[str] = None,
    fallback_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Merge `updates` into the project config and persist the result.
    """
    if not isinstance(updates, dict):
        raise ValueError("updates must be a dict")
    entry = load_project_config(
        project_name,
        projects_dir=projects_dir,
        filename=filename,
        fallback_path=fallback_path,
        persist_on_fallback=False,
    )
    changed = False
    for key, value in updates.items():
        if value is None:
            continue
        if entry.get(key) != value:
            entry[key] = value
            changed = True

    if changed or not get_project_config_path(project_name, projects_dir=projects_dir, filename=filename).exists():
        path = save_project_config(
            project_name,
            entry,
            projects_dir=projects_dir,
            filename=filename,
        )
    else:
        path = get_project_config_path(project_name, projects_dir=projects_dir, filename=filename)

    return {"path": str(path), "config": entry}


def read_root_config(
    *,
    fallback_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    path = _resolve_fallback_path(fallback_path)
    if not path.exists():
        return {}
    return _load_json(path)
