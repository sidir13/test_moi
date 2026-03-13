import logging
import os
import re
from pathlib import Path
from typing import Iterator, List, Optional

from dotenv import load_dotenv
from elevenlabs import ElevenLabs

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "eleven_v3"
DEFAULT_VOICE_ID = "pqHfZKP75CvOlQylNhV4"

# ElevenLabs v3 hard limit per request
_MAX_CHARS = 4900  # slightly below 5000 for safety margin


def _split_text(text: str, max_chars: int = _MAX_CHARS) -> List[str]:
    """Split text into chunks ≤ max_chars, cutting on sentence boundaries
    (period, exclamation, question mark) when possible.

    ElevenLabs v3 Audio Tags [like this] must not be split across chunk
    boundaries — the split always happens outside brackets.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    remaining = text

    while len(remaining) > max_chars:
        # Look for the last sentence-ending punctuation within the limit
        window = remaining[:max_chars]

        # Find last sentence boundary (. ! ?) not inside square brackets
        best_cut = -1
        in_bracket = 0
        for i, ch in enumerate(window):
            if ch == "[":
                in_bracket += 1
            elif ch == "]":
                in_bracket = max(0, in_bracket - 1)
            elif ch in ".!?" and in_bracket == 0:
                best_cut = i + 1  # cut after the punctuation

        if best_cut == -1:
            # No sentence boundary found — fall back to last whitespace
            last_space = window.rfind(" ")
            best_cut = last_space if last_space > 0 else max_chars

        chunk = remaining[:best_cut].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[best_cut:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


def eleven_labs_tts(
    text: str,
    voice_id: str = DEFAULT_VOICE_ID,
    *,
    output_path: Optional[str] = None,
    model_id: str = DEFAULT_MODEL,
) -> dict:
    """Generate speech through the ElevenLabs API and store it locally.

    If the text exceeds the 5000-character limit for ElevenLabs v3, it is
    automatically split into chunks which are concatenated into a single
    audio file.
    """
    if not text or not text.strip():
        raise ValueError("text must be provided")

    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise EnvironmentError("ELEVENLABS_API_KEY must be set in the environment")

    client = ElevenLabs(api_key=api_key)

    target_path = (
        Path(output_path)
        if output_path
        else Path("data/generated_speech/elevenlabs_output.mp3")
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)

    chunks = _split_text(text)

    if len(chunks) == 1:
        logger.info("ElevenLabs TTS: single chunk (%d chars)", len(chunks[0]))
        audio_iter = client.text_to_speech.convert(
            voice_id=voice_id,
            model_id=model_id,
            text=chunks[0],
            output_format="mp3_44100_128",
        )
        with open(target_path, "wb") as fh:
            for piece in audio_iter:
                fh.write(piece)
    else:
        logger.info(
            "ElevenLabs TTS: text split into %d chunks (total %d chars)",
            len(chunks),
            len(text),
        )
        with open(target_path, "wb") as fh:
            for idx, chunk in enumerate(chunks, 1):
                logger.info(
                    "ElevenLabs TTS: sending chunk %d/%d (%d chars)",
                    idx,
                    len(chunks),
                    len(chunk),
                )
                audio_iter = client.text_to_speech.convert(
                    voice_id=voice_id,
                    model_id=model_id,
                    text=chunk,
                    output_format="mp3_44100_128",
                )
                for piece in audio_iter:
                    fh.write(piece)

    return {
        "status": "done",
        "path": str(target_path),
        "voice_id": voice_id,
        "model_id": model_id,
        "chunks": len(chunks),
    }
