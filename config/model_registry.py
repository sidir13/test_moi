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
        "openrouterId": "anthropic/claude-opus-4.6",
        "label": "Claude Opus 4.6",
        "provider": "Anthropic",
        "description": "Nouveau modèle Opus (4.6) — meilleur pour longues narrations complexes",
        "maxTokens": 8000,
        "defaultTemperature": 0.8,
    },
    "sonnet": {
        "id": "sonnet",
        "openrouterId": "anthropic/claude-sonnet-4.6",
        "label": "Claude Sonnet 4.6",
        "provider": "Anthropic",
        "description": "Version 4.6 — compromis vitesse/qualité pour itérations rapides",
        "maxTokens": 8000,
        "defaultTemperature": 0.7,
    },
    "mistral": {
        "id": "mistral",
        "openrouterId": "mistralai/mistral-large-2512",
        "label": "Mistral Large 25.12",
        "provider": "Mistral AI",
        "description": "Grand modèle Mistral — style plus direct, très bon raisonnement",
        "maxTokens": 8000,
        "defaultTemperature": 0.7,
    },
    "gemini": {
        "id": "gemini",
        "openrouterId": "google/gemini-3.1-pro-preview",
        "label": "Gemini 3.1 Pro Preview",
        "provider": "Google",
        "description": "Dernier Gemini — narration factuelle solide et multilingue",
        "maxTokens": 8000,
        "defaultTemperature": 0.7,
    },
    "gpt5": {
        "id": "gpt5",
        "openrouterId": "openai/gpt-5.2",
        "label": "GPT‑5.2",
        "provider": "OpenAI",
        "description": "GPT‑5.2 — très créatif, utile pour variations complexes",
        "maxTokens": 8000,
        "defaultTemperature": 0.75,
    },
    "qwen": {
        "id": "qwen",
        "openrouterId": "qwen/qwen3.5-397b-a17b",
        "label": "Qwen 3.5 397B",
        "provider": "Alibaba Qwen",
        "description": "Grand modèle Qwen — narrations riches, forte couverture multilingue",
        "maxTokens": 8000,
        "defaultTemperature": 0.75,
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
