"""Load and expose the multi-step workflow definition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional


class StepConfigRegistry:
    def __init__(self, config_path: Path) -> None:
        self.config_path = Path(config_path)
        self.steps: List[Dict[str, object]] = []
        self._load()

    def _load(self) -> None:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Missing step configuration file: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.steps = data.get("steps", [])

    def find_step(self, step_id: str) -> Optional[Dict[str, object]]:
        for step in self.steps:
            if step.get("id") == step_id:
                return step
        return None

    def get_automations(self, step_id: str) -> List[str]:
        step = self.find_step(step_id)
        if not step:
            return []
        return step.get("automations", [])

    def get_skills(self, step_id: str) -> List[str]:
        step = self.find_step(step_id)
        if not step:
            return []
        return step.get("skills", [])
