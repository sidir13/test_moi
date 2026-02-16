"""
Registry of LLM models available via OpenRouter for scenario generation.

Each entry maps a short key to an OpenRouter model ID plus metadata.
The key is what the frontend / API sends; the value is used by the orchestrator.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
#  Model definitions  –  add or remove models here
# ──────────────────────────────────────────────────────────────────────

AVAILABLE_MODELS: Dict[str, Dict[str, Any]] = {
    "opus": {
        "id": "opus",
        "openrouterId": "anthropic/claude-opus-4-5",
        "label": "Claude Opus 4.5",
        "provider": "Anthropic",
        "description": "Modèle le plus puissant d'Anthropic — qualité narrative maximale",
        "maxTokens": 8000,
        "defaultTemperature": 0.8,
    },
    "sonnet": {
        "id": "sonnet",
        "openrouterId": "anthropic/claude-sonnet-4-5",
        "label": "Claude Sonnet 4.5",
        "provider": "Anthropic",
        "description": "Bon équilibre qualité / vitesse / coût",
        "maxTokens": 8000,
        "defaultTemperature": 0.7,
    },
    "gemini": {
        "id": "gemini",
        "openrouterId": "google/gemini-2.5-pro",
        "label": "Gemini 2.5 Pro",
        "provider": "Google",
        "description": "Modèle Google — très bonne capacité de raisonnement",
        "maxTokens": 8000,
        "defaultTemperature": 0.7,
    },
}

# Default model key when none is specified
DEFAULT_MODEL_KEY = "opus"


# ──────────────────────────────────────────────────────────────────────
#  Public helpers
# ──────────────────────────────────────────────────────────────────────

def get_available_models() -> List[Dict[str, Any]]:
    """Return the list of models for the frontend."""
    return list(AVAILABLE_MODELS.values())


def resolve_model_id(key: Optional[str] = None) -> str:
    """
    Resolve a short key (e.g. ``"opus"``) into the full OpenRouter model ID.

    Falls back to ``DEFAULT_MODEL_KEY`` when *key* is ``None`` or unknown.
    """
    if not key:
        key = DEFAULT_MODEL_KEY

    entry = AVAILABLE_MODELS.get(key)
    if entry:
        return entry["openrouterId"]

    # Maybe the caller already passed a full OpenRouter ID
    known_ids = {m["openrouterId"] for m in AVAILABLE_MODELS.values()}
    if key in known_ids:
        return key

    logger.warning("Unknown model key '%s' — falling back to '%s'", key, DEFAULT_MODEL_KEY)
    return AVAILABLE_MODELS[DEFAULT_MODEL_KEY]["openrouterId"]


def get_model_config(key: Optional[str] = None) -> Dict[str, Any]:
    """Return the full config dict for a model key."""
    if not key:
        key = DEFAULT_MODEL_KEY
    return AVAILABLE_MODELS.get(key, AVAILABLE_MODELS[DEFAULT_MODEL_KEY])
