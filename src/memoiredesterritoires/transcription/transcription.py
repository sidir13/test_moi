import base64
from pydub import AudioSegment
from openai import OpenAI
import os
from dotenv import load_dotenv
import tempfile
import math

def transcribe_audio(
    audio_path: str,
    chunk_duration_s: int = 30,
    model: str = "google/gemini-3-flash-preview",
) -> str:
    """
    Transcribe a WAV file in chunks, adding continuous timestamps [mm:ss] to each line.
    """
    load_dotenv()
    client = OpenAI(
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        base_url="https://openrouter.ai/api/v1"
    )

    system_prompt = """Tu es un système de transcription automatique.
Transcris fidèlement la parole humaine.
- Ne résume pas
- Ne reformule pas
- Ne corrige pas
- Garde les hésitations et répétitions
Répond uniquement par le texte transcrit en français."""

    if chunk_duration_s <= 0:
        raise ValueError("chunk_duration_s must be positive")

    chunk_duration_ms = int(chunk_duration_s) * 1000
    audio = AudioSegment.from_wav(audio_path)

    # Split audio into chunks
    chunks = [
        audio[i:i + chunk_duration_ms]
        for i in range(0, len(audio), chunk_duration_ms)
    ]
    
    full_transcript = []
    cumulative_ms = 0  # cumulative time in milliseconds

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, chunk in enumerate(chunks, 1):
            print(f"Chunk {i}/{len(chunks)} | durée = {len(chunk)/1000:.1f}s")
            chunk_path = os.path.join(tmpdir, f"chunk_{i}.wav")
            chunk.export(chunk_path, format="wav")

            with open(chunk_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")

            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Transcris exactement ce segment audio n°{i}."},
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": encoded,
                                    "format": "wav"
                                }
                            }
                        ]
                    }
                ]
            )

            # Get plain text from LLM
            text = completion.choices[0].message.content.strip()
            lines = text.split("\n")  # split into lines for timestamping

            # Add continuous timestamps
            for line in lines:
                if not line.strip():
                    continue
                # compute mm:ss from cumulative_ms
                total_seconds = cumulative_ms // 1000
                mm = total_seconds // 60
                ss = total_seconds % 60
                full_transcript.append(f"[{mm:02d}:{ss:02d}] {line}")
                # Increment cumulative_ms assuming approx. even spacing
                # Here we divide chunk length evenly across lines
                cumulative_ms += len(chunk) // max(len(lines), 1)

    return "\n".join(full_transcript)
