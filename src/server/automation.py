"""Automation runner that triggers backend skills per step."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from memoiredesterritoires.json_utils.read_json import read_json_file
from memoiredesterritoires.project_notes.update_project_notes import update_project_notes as skill_update_project_notes
from memoiredesterritoires.project_config_builder import ScenarioConfigBuilderSkill

logger = logging.getLogger(__name__)


class AutomationRunner:
    def __init__(self, step_registry, settings) -> None:
        self.step_registry = step_registry
        self.settings = settings
        self.config_builder = ScenarioConfigBuilderSkill()

    def ensure_project_exists(self, project_name: str) -> None:
        project_path = self.settings.projects_dir / project_name
        project_path.mkdir(parents=True, exist_ok=True)
        (project_path / "audio").mkdir(exist_ok=True)
        (project_path / "notes").mkdir(exist_ok=True)
        (project_path / "outputs").mkdir(exist_ok=True)

    def update_project_notes(self, project_name: str, description: str) -> Dict[str, object]:
        if not description:
            return {"status": "skipped", "reason": "empty description"}
        return skill_update_project_notes(project_name, description)

    def run(self, step_id: str, project_name: str, payload: Optional[dict]) -> List[Dict[str, object]]:
        automations = self.step_registry.get_automations(step_id)
        results: List[Dict[str, object]] = []
        for action in automations:
            handler = getattr(self, f"_handle_{action}", None)
            if not handler:
                logger.warning("No automation handler for %s", action)
                results.append({"action": action, "status": "skipped"})
                continue
            try:
                result = handler(project_name, payload or {})
                if isinstance(result, dict):
                    result.setdefault("action", action)
                    results.append(result)
                else:
                    results.append({"action": action, "status": "ok", "result": result})
            except Exception as exc:
                logger.exception("Automation %s failed", action)
                results.append({"action": action, "status": "error", "error": str(exc)})
        return results

    def _handle_initialize_project_workspace(self, project_name: str, payload: dict) -> Dict[str, object]:
        self.ensure_project_exists(project_name)
        return {"status": "ok", "message": "Project workspace ready"}

    def _handle_update_project_notes(self, project_name: str, payload: dict) -> Dict[str, object]:
        description = payload.get("notes") or payload.get("description")
        if not description:
            return {"status": "skipped", "reason": "no notes provided"}
        return self.update_project_notes(project_name, description)

    def _handle_read_project_config(self, project_name: str, payload: dict) -> Dict[str, object]:
        config_path = self.settings.config_json
        content = read_json_file(str(config_path), project_name=project_name)
        return {"status": "ok", "config_keys": list(content.get("content", {}).keys())}

    def _handle_project_config_builder(self, project_name: str, payload: dict) -> Dict[str, object]:
        description = payload.get("notes") or payload.get("description")
        if not description:
            return {"status": "skipped", "reason": "no description"}
        try:
            result = self.config_builder.run({
                "project_description": description,
                "project_name": project_name,
                "mode": payload.get("mode", "simple"),
            })
            return {"status": "ok", "config_path": result.get("config_path")}
        except Exception as exc:
            logger.warning("ScenarioConfigBuilderSkill failed: %s", exc)
            return {"status": "skipped", "reason": str(exc)}

    def _handle_placeholder(self, project_name: str, payload: dict) -> Dict[str, object]:
        return {"status": "ok", "message": "placeholder automation"}

    # Map remaining automation names to placeholder handler to keep JSON simple
    _alias_actions = [
        "transcription_pipeline",
        "analysis_storage",
        "analysis_storage_background",
        "analysis_storage_query",
        "scenario_maker",
        "background_sound_finder",
        "voice_instructions",
        "adjust_audio_volume",
        "text_to_speech_with_instructions",
        "insert_background_sounds",
        "ensure_final_assets",
    ]

    for action in _alias_actions:
        locals()[f"_handle_{action}"] = _handle_placeholder
