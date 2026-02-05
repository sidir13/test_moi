"""Utility to load JSON files with minimal validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def read_json_file(path: str, *, key: Optional[str] = None, project_name: Optional[str] = None) -> Dict[str, Any]:
    """Read a JSON file from disk and optionally extract a key (optionally scoped to a project)."""

    json_path = Path(path)
    if not json_path.exists():
        raise FileNotFoundError(f"Fichier JSON introuvable: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    target = data
    if project_name is not None:
        if project_name not in data:
            raise KeyError(f"Projet '{project_name}' absent dans {json_path}")
        target = data[project_name]

    if key is not None:
        if key not in target:
            raise KeyError(f"Clé '{key}' absente dans {json_path} (projet={project_name})")
        content = target[key]
    else:
        content = target

    return {"path": str(json_path), "project": project_name, "key": key, "content": content}
