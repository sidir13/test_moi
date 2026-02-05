"""Utility to load JSON files with minimal validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def read_json_file(path: str, *, key: Optional[str] = None) -> Dict[str, Any]:
    """Read a JSON file from disk and optionally extract a key."""

    json_path = Path(path)
    if not json_path.exists():
        raise FileNotFoundError(f"Fichier JSON introuvable: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if key is not None:
        if key not in data:
            raise KeyError(f"Clé '{key}' absente dans {json_path}")
        value = data[key]
    else:
        value = data

    return {
        "path": str(json_path),
        "key": key,
        "content": value,
    }
