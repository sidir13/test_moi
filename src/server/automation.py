"""Automation runner that triggers backend skills per step."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from memoiredesterritoires.project_notes.update_project_notes import update_project_notes as skill_update_project_notes
from memoiredesterritoires.project_config_builder import ScenarioConfigBuilderSkill
from memoiredesterritoires.project_config import (
    get_project_config_path,
    load_project_config,
    save_project_config,
)

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
        result: Dict[str, object] = {"status": "skipped", "reason": "no notes provided"}
        if description:
            result = self.update_project_notes(project_name, description)
        pref_result = self._apply_project_preferences(project_name, payload)
        if pref_result:
            result.setdefault("updates", {}).update(pref_result)
        return result

    def _apply_project_preferences(self, project_name: str, payload: dict) -> Dict[str, object]:
        audience = payload.get("audience")
        tone = payload.get("tone")
        target_duration = payload.get("target_duration")
        voice_instructions = payload.get("voice_instructions")
        tts_provider = payload.get("tts_provider")
        tts_voice_id = payload.get("tts_voice_id")
        include_citations = payload.get("include_citations")
        source_usage_level = payload.get("source_usage_level")
        if isinstance(tts_provider, str):
            tts_provider = tts_provider.strip().lower()
        if isinstance(tts_voice_id, str):
            tts_voice_id = tts_voice_id.strip()
        has_updates = any(
            value is not None and (value != "" if isinstance(value, str) else True)
            for value in (audience, tone, target_duration, voice_instructions, tts_provider, tts_voice_id,
                          include_citations, source_usage_level)
        )
        if not has_updates:
            return {}

        entry = load_project_config(
            project_name,
            projects_dir=self.settings.projects_dir,
            fallback_path=self.settings.config_json,
        )
        scenario_config = entry.setdefault("scenario_config", {})
        gen_params = scenario_config.setdefault("generation_parameters", {})
        updated: Dict[str, object] = {}
        changed = False

        if isinstance(audience, str) and audience.strip():
            audience_value = audience.strip()
            entry["audience"] = audience_value
            public_param = gen_params.setdefault("public_cible", {})
            public_param["value"] = audience_value
            public_param["user_specified"] = True
            updated["audience"] = audience_value
            changed = True

        if isinstance(tone, str) and tone.strip():
            tone_value = tone.strip()
            entry["tone"] = tone_value
            tone_param = gen_params.setdefault("ton", {})
            tone_param["value"] = tone_value
            tone_param["user_specified"] = True
            updated["tone"] = tone_value
            changed = True

        if isinstance(target_duration, (int, float)):
            duration_value = int(target_duration)
            if duration_value <= 0:
                duration_value = 30
            duration_value = max(30, min(600, duration_value))
            duration_param = gen_params.setdefault("duree", {})
            duration_param["value"] = duration_value
            duration_param["user_specified"] = True
            entry["target_duration"] = duration_value
            updated["target_duration"] = duration_value
            changed = True

        if voice_instructions is not None:
            voice_value = voice_instructions.strip()
            if voice_value:
                entry["voice_instructions"] = voice_value
                entry["voice_instructions_source"] = "manual"
                updated["voice_instructions"] = "manual"
                changed = True

        allowed_providers = {"qwen", "elevenlabs"}
        if tts_provider in allowed_providers:
            entry["tts_provider"] = tts_provider
            updated["tts_provider"] = tts_provider
            if tts_provider != "elevenlabs":
                entry.pop("tts_voice_id", None)
            changed = True

        if tts_voice_id and (tts_provider == "elevenlabs" or entry.get("tts_provider") == "elevenlabs"):
            entry["tts_voice_id"] = tts_voice_id
            updated["tts_voice_id"] = tts_voice_id
            changed = True

        if isinstance(include_citations, bool):
            entry["include_citations"] = include_citations
            updated["include_citations"] = include_citations
            changed = True

        allowed_source_levels = {"leger", "modere", "central"}
        if isinstance(source_usage_level, str) and source_usage_level in allowed_source_levels:
            entry["source_usage_level"] = source_usage_level
            updated["source_usage_level"] = source_usage_level
            changed = True

        if changed:
            save_project_config(
                project_name,
                entry,
                projects_dir=self.settings.projects_dir,
            )
            logger.info(
                "Project preferences updated | project=%s audience=%s tone=%s target_duration=%s voice_manual=%s",
                project_name,
                entry.get("audience"),
                entry.get("tone"),
                entry.get("target_duration"),
                bool(entry.get("voice_instructions")),
            )
        return updated

    def _handle_read_project_config(self, project_name: str, payload: dict) -> Dict[str, object]:
        entry = load_project_config(
            project_name,
            projects_dir=self.settings.projects_dir,
            fallback_path=self.settings.config_json,
        )
        config_path = get_project_config_path(project_name, projects_dir=self.settings.projects_dir)
        return {
            "status": "ok",
            "config_path": str(config_path),
            "config_keys": sorted(entry.keys()),
        }

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

    def _handle_transcription_pipeline(self, project_name: str, payload: dict) -> Dict[str, object]:
        import json
        from memoiredesterritoires.analysis_storage.analysis_storage import fetch_analysis_results
        from memoiredesterritoires.transcription.transcription_event_extraction import extract_events_robust

        data = fetch_analysis_results(
            analysis_type="transcription",
            source_path_contains=project_name,
            limit=50,
        )
        texts = [
            e["result"]["transcription"]
            for e in data.get("entries", [])
            if isinstance(e.get("result"), dict) and e["result"].get("transcription")
        ]
        combined = "\n\n".join(texts)
        if not combined.strip():
            return {"status": "skipped", "reason": "no transcriptions available"}

        try:
            events_data = extract_events_robust(combined)
        except Exception as exc:
            logger.warning("Event extraction failed for %s: %s", project_name, exc)
            return {"status": "skipped", "reason": str(exc)}

        nodes: Dict[str, object] = {}
        edges: list = []
        for i, event in enumerate(events_data.get("events", [])):
            eid = f"event_{i}"
            nodes[eid] = {
                "id": eid,
                "name": event.get("title", eid),
                "type": "Event",
                "description": event.get("description", ""),
                "time": event.get("approximate_time", ""),
            }
            for actor in event.get("actors", []):
                if actor not in nodes:
                    nodes[actor] = {"id": actor, "name": actor, "type": "Person"}
                edges.append({"id": f"actor_{i}_{actor}", "source": actor, "target": eid, "type": "PARTICIPATED_IN"})
            for place in event.get("places", []):
                if place not in nodes:
                    nodes[place] = {"id": place, "name": place, "type": "Place"}
                edges.append({"id": f"place_{i}_{place}", "source": eid, "target": place, "type": "HAPPENED_IN"})
            for kw in event.get("keywords", []):
                if kw not in nodes:
                    nodes[kw] = {"id": kw, "name": kw, "type": "Keyword"}
                edges.append({"id": f"kw_{i}_{kw}", "source": eid, "target": kw, "type": "HAS_TOPIC"})

        graph_data = {"nodes": list(nodes.values()), "edges": edges}
        project_path = self.settings.projects_dir / project_name
        (project_path / "events.json").write_text(json.dumps(events_data, ensure_ascii=False, indent=2))
        (project_path / "graph.json").write_text(json.dumps(graph_data, ensure_ascii=False, indent=2))

        logger.info("Knowledge graph saved | project=%s events=%d nodes=%d",
                    project_name, len(events_data.get("events", [])), len(nodes))
        return {"status": "ok", "event_count": len(events_data.get("events", []))}

    def _handle_placeholder(self, project_name: str, payload: dict) -> Dict[str, object]:
        return {"status": "ok", "message": "placeholder automation"}

    # Map remaining automation names to placeholder handler to keep JSON simple
    _alias_actions = [
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
