import sys
import base64
from openai import OpenAI
import os
from dotenv import load_dotenv


def analyse_audio_industriel(audio_path: str) -> str:
    load_dotenv()
    client = OpenAI(
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
        base_url="https://openrouter.ai/api/v1"
    )

    with open(audio_path, "rb") as f:
        wav_data = f.read()

    encoded_string = base64.b64encode(wav_data).decode("utf-8")

    completion = client.chat.completions.create(
        model="google/gemini-3-flash-preview",
        messages=[
            {
                "role": "system",
                "content": """Tu es un expert en analyse sonore industrielle et historique.
Contexte : Cet enregistrement provient d'archives d'entretiens d'ouvriers 
et de bruits d'ambiance en chantier navale.
Mission : Fournis une description précise des sons entendus, identifie 
les activités en arrière-plan et essaie de nommer l'outil ou la machine 
spécifique (ex: meuleuse, tour, perceuse pneumatique, etc.). 
Répond impérativement en français."""
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyse cet enregistrement et identifie l'outil utilisé."},
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": encoded_string,
                            "format": "wav"
                        }
                    }
                ]
            }
        ]
    )

    return completion.choices[0].message.content


if __name__ == "__main__":
    audio_path = "path/to/your/audio.wav"

    result = analyze_audio(audio_path)
    print("\n=== Résultat de l'analyse ===\n")
    print(result)
