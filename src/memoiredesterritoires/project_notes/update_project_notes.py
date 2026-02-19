"""Store user descriptions / guidance for a project in its config.json."""

from __future__ import annotations

from typing import Optional

from memoiredesterritoires.project_config import (
    DEFAULT_PROJECT_NAME,
    load_project_config,
    save_project_config,
)

DEFAULT_PROJECT = DEFAULT_PROJECT_NAME


def update_project_notes(
    project_name: Optional[str],
    description: str,
) -> dict:
    """Persist a free-form description / requirements block for the project."""

    if not description or not description.strip():
        raise ValueError("description must be provided")

    project = project_name.strip() if project_name else DEFAULT_PROJECT
    entry = load_project_config(project)
    entry["project_notes"] = description.strip()
    config_path = save_project_config(project, entry)

    return {
        "status": "updated",
        "project": project,
        "project_notes": entry["project_notes"],
        "config_path": str(config_path),
    }
