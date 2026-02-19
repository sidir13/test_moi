"""
Utility to update TTS/STT voice instructions per project.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from memoiredesterritoires.project_config import (
    DEFAULT_PROJECT_NAME,
    load_project_config,
    save_project_config,
)

DEFAULT_PROJECT = DEFAULT_PROJECT_NAME


def edit_voice_instructions(project_name: Optional[str], voice_instructions: str) -> Dict[str, Any]:
    """
    Update or create the voice_instructions block for the given project.
    """
    if not voice_instructions or not voice_instructions.strip():
        raise ValueError("voice_instructions must be provided")

    project = project_name.strip() if project_name else DEFAULT_PROJECT
    project_entry = load_project_config(project)
    project_entry["voice_instructions"] = voice_instructions.strip()
    project_entry["voice_instructions_source"] = "manual"
    config_path = save_project_config(project, project_entry)

    return {
        "status": "updated",
        "project": project,
        "voice_instructions": project_entry["voice_instructions"],
        "config_path": str(config_path),
    }
