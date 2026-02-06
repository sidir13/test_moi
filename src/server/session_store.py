"""Filesystem backed session storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionContext(BaseModel):
    session_id: str
    project_name: str
    current_step: str
    steps: Dict[str, dict] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return json.loads(self.model_dump_json())


class SessionStore:
    def __init__(self, base_path: Path) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self.base_path / f"{session_id}.json"

    def create_session(self, project_name: str, initial_step: str) -> Dict[str, object]:
        session = SessionContext(
            session_id=str(uuid4()),
            project_name=project_name,
            current_step=initial_step,
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
        data.update({k: v for k, v in updates.items() if k != "steps"})
        if "steps" in updates:
            merged_steps = data.get("steps", {})
            merged_steps.update(updates["steps"])
            data["steps"] = merged_steps
        with open(self._session_path(session_id), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return data

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
