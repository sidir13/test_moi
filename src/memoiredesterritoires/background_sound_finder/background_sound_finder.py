"""Helper to enumerate allowed background sound files."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aac"}
ROOT_DIR = Path("data/audio/background_sounds")


def find_background_sounds(keyword: Optional[str] = None, limit: int = 20) -> dict:
    """Return relative paths of available background sounds, optionally filtered."""
    if not ROOT_DIR.exists():
        raise FileNotFoundError(f"Répertoire introuvable: {ROOT_DIR}")
    if limit <= 0:
        raise ValueError("limit must be positive")

    keyword_lower = keyword.lower() if keyword else None
    results: List[str] = []

    root_resolved = ROOT_DIR.resolve()
    project_root = Path.cwd().resolve()
    relative_prefix = Path("data/audio/background_sounds")

    for folder in sorted(root_resolved.iterdir()):
        if not folder.is_dir():
            continue
        if keyword_lower and keyword_lower not in folder.name.lower():
            # Only include folders whose names match the keyword when provided
            continue
        for file in sorted(folder.rglob("*")):
            if file.is_file() and file.suffix.lower() in AUDIO_EXTENSIONS:
                try:
                    rel_path = relative_prefix / file.relative_to(root_resolved)
                except ValueError:
                    rel_path = file.resolve().relative_to(project_root)
                results.append(str(rel_path))
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break

    return {
        "status": "ok",
        "root": str(ROOT_DIR),
        "keyword": keyword,
        "limit": limit,
        "count": len(results),
        "files": results,
    }
