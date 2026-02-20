import base64
import os
import io
import numpy as np
import librosa
import soundfile as sf
from openai import OpenAI
from dotenv import load_dotenv

# ---------------- CONFIG ----------------
CHUNK_DURATION = 5.0   # seconds
ENERGY_THRESHOLD = 0.01
SAMPLE_RATE = 16000
MODEL = "google/gemini-3-flash-preview"

# ---------------------------------------

def analyze_chunk(chunk, sr, client):
    buffer = io.BytesIO()
    sf.write(buffer, chunk, sr, format="WAV")
    buffer.seek(0)

    encoded = base64.b64encode(buffer.read()).decode("utf-8")

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": """Tu es un expert en analyse sonore industrielle.
Ignore les silences et conversations lointaines.
Décris uniquement les outils ou machines clairement audibles."""
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Quel outil est utilisé dans ce son ?"},
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

    return completion.choices[0].message.content.strip()


def analyse_audio_industriel(audio_path: str):
    load_dotenv()
    client = OpenAI(
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        base_url="https://openrouter.ai/api/v1"
    )

    # Load audio
    y, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
    y, _ = librosa.effects.trim(y, top_db=30)
    chunk_size = int(CHUNK_DURATION * sr)

    # -------- FAST RMS ENERGY SCAN --------
    rms = librosa.feature.rms(
        y=y,
        frame_length=chunk_size,
        hop_length=chunk_size
    )[0]

    best_idx = int(np.argmax(rms))
    best_energy = float(rms[best_idx])

    if best_energy < ENERGY_THRESHOLD:
        return "Aucun outil clairement détecté."

    i = best_idx * chunk_size
    chunk = y[i:i+chunk_size]
    start = i / sr
    end = (i + len(chunk)) / sr

    description = analyze_chunk(chunk, sr, client)

    return {
        "start": round(start, 2),
        "end": round(end, 2),
        "description": description
        
    }


def relevant_audio(audiopath):
    audio_path = audiopath
    result = analyse_audio_industriel(audio_path)

    if isinstance(result, dict):
        print(f"[{result['start']}s - {result['end']}s] → {result['description']}")
    else:
        print(result)

    
