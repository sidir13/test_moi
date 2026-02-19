"""
Text-to-speech helper that adapts pronunciation/voice based on user instructions.
"""

from __future__ import annotations

import re
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import logging

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

from memoiredesterritoires.project_config import (
    DEFAULT_PROJECT_NAME,
    load_project_config,
)

logger = logging.getLogger(__name__)

DEFAULT_PROJECT = DEFAULT_PROJECT_NAME
LOCAL_MODEL_DIR = Path(os.getenv("QWEN_TTS_LOCAL_DIR", "models/qwen3-tts")).expanduser()
DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
_MODEL_CACHE: Dict[str, Qwen3TTSModel] = {}


def _detect_device() -> tuple[str, torch.dtype]:
    """
    Pick the most capable device available along with a numerically stable dtype.

    Note:
        Qwen TTS occasionally produces NaNs on MPS when using float16, so we keep
        float32 there even if it is slower to avoid RuntimeError during sampling.
    """
    if torch.cuda.is_available():
        return "cuda", torch.float16
    if torch.backends.mps.is_available():
        return "mps", torch.float32
    return "cpu", torch.float32


def _load_voice_instructions(project_name: Optional[str]) -> tuple[str, str]:
    project = project_name.strip() if project_name else DEFAULT_PROJECT
    entry = load_project_config(project)
    instructions = (entry or {}).get("voice_instructions")
    if not instructions:
        raise ValueError(
            f"Aucune voix définie pour '{project}'. Utilisez d'abord edit_voice_instructions."
        )
    trimmed_preview = instructions.strip().splitlines()[0][:160] if instructions else ""
    logger.info(
        "Using voice instructions for project=%s (source=%s): %s%s",
        project,
        entry.get("voice_instructions_source"),
        trimmed_preview,
        "…" if instructions and len(instructions) > len(trimmed_preview) else "",
    )
    return instructions, project


def _resolve_model_source(model_name: str) -> tuple[str, dict]:
    candidate = Path(model_name)
    if candidate.exists():
        return str(candidate), {"local_files_only": True}
    if LOCAL_MODEL_DIR.exists() and any(LOCAL_MODEL_DIR.iterdir()):
        return str(LOCAL_MODEL_DIR), {"local_files_only": True}
    LOCAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return model_name, {"cache_dir": str(LOCAL_MODEL_DIR)}


def _load_model(model_source: str, device: str, dtype: torch.dtype, source_kwargs: dict) -> Qwen3TTSModel:
    cache_key = f"{model_source}:{device}:{dtype}"
    model = _MODEL_CACHE.get(cache_key)
    if model is None:
        model = Qwen3TTSModel.from_pretrained(
            model_source,
            device_map=device,
            dtype=dtype,
            attn_implementation="sdpa",
            **source_kwargs,
        )
        _MODEL_CACHE[cache_key] = model
    return model


def text_to_speech_with_instructions(
    text: str,
    *,
    project_name: Optional[str] = None,
    language: str = "French",
    output_path: Optional[str] = None,
    model_name: str = DEFAULT_MODEL,
) -> dict[str, str | int]:
    """
    Generate speech for `text` while honoring expressive `instructions`.

    Args:
        text: Transcript to synthesize.
        instructions: Voice/acting cues (tone, age, energy, pacing, etc.).
        language: Target language to steer pronunciation (default French).
        output_path: Optional destination for the WAV file.
        model_name: Hugging Face identifier for the Qwen3 TTS model to load.

    Returns:
        Metadata describing the synthesized clip.
    """
    if not text or not text.strip():
        raise ValueError("text must be provided")
    instructions, project = _load_voice_instructions(project_name)

    device, dtype = _detect_device()
    model_source, source_kwargs = _resolve_model_source(model_name)
    model = _load_model(model_source, device, dtype, source_kwargs)

    wavs, sample_rate = model.generate_voice_design(
        text=text,
        language=language,
        instruct=instructions,
    )

    if output_path is None:
        safe_snippet = re.sub(r"[^a-z0-9]+", "-", instructions.lower()).strip("-")[:30]
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        output_dir = Path("data/generated_speech")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"tts_{safe_snippet or 'voice'}_{timestamp}.wav"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    sf.write(str(output_path), wavs[0], sample_rate)

    return {
        "status": "generated",
        "path": str(output_path),
        "language": language,
        "sample_rate": sample_rate,
        "num_samples": len(wavs[0]),
        "project": project,
        "instructions": instructions,
    }
