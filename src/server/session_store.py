"""Filesystem backed session storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionContext(BaseModel):
    session_id: str
    project_name: str
    current_step: str
    steps: Dict[str, dict] = Field(default_factory=dict)
    chat_history: list = Field(default_factory=list)
    scenario_target: int = Field(default=3)
    scenarios: List[dict] = Field(default_factory=list)
    selected_scenario: Optional[dict] = None
    scenario_progress: List[dict] = Field(default_factory=list)
    scenario_audio: Optional[dict] = None
    scenario_images: List[dict] = Field(default_factory=list)
    scenario_slideshow: Optional[dict] = None

    def to_dict(self) -> Dict[str, object]:
        return json.loads(self.model_dump_json())


def _scenarios_equal(a: Optional[dict], b: Optional[dict]) -> bool:
    if a is b:
        return True
    if a is None or b is None:
        return False
    try:
        return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)
    except TypeError:
        return a == b


class SessionStore:
    def __init__(self, base_path: Path) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self.base_path / f"{session_id}.json"

    def create_session(self, project_name: str, initial_step: str, scenario_target: int = 3) -> Dict[str, object]:
        session = SessionContext(
            session_id=str(uuid4()),
            project_name=project_name,
            current_step=initial_step,
            scenario_target=scenario_target,
        )
        self._write(session)
        return session.to_dict()

    def load_session(self, session_id: str) -> Optional[Dict[str, object]]:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def update_session(self, session_id: str, updates: Dict[str, dict]) -> Dict[str, object]:
        data = self.load_session(session_id)
        if not data:
            raise FileNotFoundError(f"Session {session_id} not found")
        data.update({k: v for k, v in updates.items() if k not in {"steps", "chat_history"}})
        if "steps" in updates:
            merged_steps = data.get("steps", {})
            merged_steps.update(updates["steps"])
            data["steps"] = merged_steps
        if "chat_history" in updates:
            data["chat_history"] = updates["chat_history"]
        with open(self._session_path(session_id), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    def get_chat_history(self, session_id: str) -> list:
        data = self.load_session(session_id)
        if not data:
            return []
        return data.get("chat_history", [])

    def save_chat_history(self, session_id: str, history: list) -> None:
        self.update_session(session_id, {"chat_history": history})

    def get_scenarios(self, session_id: str) -> List[dict]:
        data = self.load_session(session_id)
        if not data:
            return []
        return data.get("scenarios", [])

    def set_selected_scenario(self, session_id: str, scenario: dict) -> None:
        data = self.load_session(session_id)
        if not data:
            raise FileNotFoundError(f"Session {session_id} not found")
        previous = data.get("selected_scenario")
        updates: Dict[str, object] = {"selected_scenario": scenario}
        if not _scenarios_equal(previous, scenario):
            updates["scenario_audio"] = None
        self.update_session(session_id, updates)

    def init_scenario_progress(self, session_id: str, steps: List[Dict[str, str]]) -> None:
        templated = []
        for step in steps:
            templated.append({
                "label": step.get("label", "Étape"),
                "status": step.get("status", "pending"),
                "message": step.get("message", ""),
            })
        self.update_session(session_id, {"scenario_progress": templated})

    def update_scenario_progress(self, session_id: str, index: int, status: str, message: Optional[str] = None) -> None:
        data = self.load_session(session_id)
        if not data:
            return
        progress = data.get("scenario_progress", [])
        if 0 <= index < len(progress):
            progress[index]["status"] = status
            if message is not None:
                progress[index]["message"] = message
            self.update_session(session_id, {"scenario_progress": progress})

    def get_scenario_progress(self, session_id: str) -> List[dict]:
        data = self.load_session(session_id)
        if not data:
            return []
        return data.get("scenario_progress", [])

    def save_scenario_audio(self, session_id: str, metadata: dict) -> None:
        self.update_session(session_id, {"scenario_audio": metadata})

    def get_scenario_audio(self, session_id: str) -> Optional[dict]:
        data = self.load_session(session_id)
        if not data:
            return None
        return data.get("scenario_audio")

    def save_agent_outputs(self, session_id: str, agent_outputs: dict) -> None:
        """Store the intermediate outputs of each agent for inspection."""
        self.update_session(session_id, {"agent_outputs": agent_outputs})

    def get_agent_outputs(self, session_id: str) -> Optional[dict]:
        data = self.load_session(session_id)
        if not data:
            return None
        return data.get("agent_outputs")

    def append_project_file(self, project_name: str, file_path: str) -> None:
        project_meta_path = self.base_path / f"{project_name}_files.json"
        payload = []
        if project_meta_path.exists():
            with open(project_meta_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        payload.append(file_path)
        with open(project_meta_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def _write(self, session: SessionContext) -> None:
        with open(self._session_path(session.session_id), "w", encoding="utf-8") as f:
            f.write(session.model_dump_json(indent=2))


def get_session_store() -> SessionStore:
    from .config import get_settings

    settings = get_settings()
    return SessionStore(settings.session_store)
