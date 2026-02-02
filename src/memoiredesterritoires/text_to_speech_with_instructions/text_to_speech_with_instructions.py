"""
Text-to-speech helper that adapts pronunciation/voice based on user instructions.
"""

from __future__ import annotations

import re
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

DEFAULT_PROJECT = "Mémoire des Territoires"
CONFIG_PATH = Path(__file__).resolve().parents[3] / "config.json"


def _detect_device() -> tuple[str, torch.dtype]:
    """Pick the most capable device available along with the right dtype."""
    if torch.cuda.is_available():
        return "cuda", torch.float16
    if torch.backends.mps.is_available():
        return "mps", torch.float16
    return "cpu", torch.float32


def _load_voice_instructions(project_name: Optional[str]) -> tuple[str, str]:
    project = project_name.strip() if project_name else DEFAULT_PROJECT
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"config.json introuvable: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    entry = config.get(project)
    if not entry or not entry.get("voice_instructions"):
        raise ValueError(
            f"Aucune voix définie pour '{project}'. Utilisez d'abord edit_voice_instructions."
        )
    return entry["voice_instructions"], project


def text_to_speech_with_instructions(
    text: str,
    *,
    project_name: Optional[str] = None,
    language: str = "French",
    output_path: Optional[str] = None,
    model_name: str = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
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
    model = Qwen3TTSModel.from_pretrained(
        model_name,
        device_map=device,
        dtype=dtype,
        attn_implementation="sdpa",
    )

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
