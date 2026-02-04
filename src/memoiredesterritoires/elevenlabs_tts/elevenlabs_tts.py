import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from elevenlabs import ElevenLabs


DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_VOICE_ID = "pqHfZKP75CvOlQylNhV4"


def eleven_labs_tts(
    text: str,
    voice_id: str = DEFAULT_VOICE_ID,
    *,
    output_path: Optional[str] = None,
    model_id: str = DEFAULT_MODEL,
) -> dict:
    """Generate speech through the ElevenLabs API and store it locally."""

    if not text or not text.strip():
        raise ValueError("text must be provided")

    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise EnvironmentError("ELEVENLABS_API_KEY must be set in the environment")

    client = ElevenLabs(api_key=api_key)

    target_path = Path(output_path) if output_path else Path("data/generated_speech/elevenlabs_output.mp3")
    target_path.parent.mkdir(parents=True, exist_ok=True)

    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id=model_id,
        text=text,
        output_format="mp3_44100_128",
    )

    with open(target_path, "wb") as fh:
        for chunk in audio:
            fh.write(chunk)

    return {
        "status": "generated",
        "path": str(target_path),
        "voice_id": voice_id,
        "model_id": model_id,
    }
