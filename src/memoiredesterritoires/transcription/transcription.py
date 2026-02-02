import base64
from pydub import AudioSegment
from openai import OpenAI
import os
from dotenv import load_dotenv
import tempfile


def transcribe_audio(
    audio_path,
    api_key,
    chunk_duration_ms=30000,
    model="google/gemini-3-flash-preview"
):
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
Pour chaque phrase :
- ajoute un timestamp relatif au début du segment
- format : [mm:ss] texte
Répond uniquement par le texte transcrit en français."""

    audio = AudioSegment.from_wav(audio_path)

    chunks = [
        audio[i:i + chunk_duration_ms]
        for i in range(0, len(audio), chunk_duration_ms)
    ]
    
    full_transcript = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, chunk in enumerate(chunks, 1):
            print(f"Chunk {i} / {len(chunks)} | durée = {len(chunk)/1000:.1f}s")
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

            text = completion.choices[0].message.content
            full_transcript.append(f"\n[CHUNK {i}]\n{text}")

    return "\n".join(full_transcript)
