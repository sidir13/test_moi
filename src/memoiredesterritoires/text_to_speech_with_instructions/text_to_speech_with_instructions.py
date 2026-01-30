"""
Text-to-speech helper that adapts pronunciation/voice based on user instructions.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


def _detect_device() -> tuple[str, torch.dtype]:
    """Pick the most capable device available along with the right dtype."""
    if torch.cuda.is_available():
        return "cuda", torch.float16
    if torch.backends.mps.is_available():
        return "mps", torch.float16
    return "cpu", torch.float32


def text_to_speech_with_instructions(
    text: str,
    instructions: str,
    *,
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
    if not instructions or not instructions.strip():
        raise ValueError("instructions must be provided")

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
        "instructions": instructions,
    }
