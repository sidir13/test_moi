import base64
from openai import OpenAI
import os
from dotenv import load_dotenv


def analyse_audio_industriel(
    file_path: str,
    context: str,
    model: str = "gpt-4o-audio-preview"
):
    """
    Analyse un fichier audio industriel et retourne la transcription/description. 
    :param file_path: chemin vers le fichier .wav
    :param context: contexte général (archives, chantier, usine, etc.)
    :param api_key: clé OpenAI
    :param model: modèle audio (par défaut gpt-4o-audio-preview)
    :return: texte d'analyse en français
    """
    load_dotenv()
    
    client = OpenAI(api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"))

    # Lecture du fichier
    with open(file_path, "rb") as f:
        wav_data = f.read()

    encoded_string = base64.b64encode(wav_data).decode("utf-8")

    completion = client.chat.completions.create(
        model=model,
        modalities=["text", "audio"],
        audio={"voice": "alloy", "format": "wav"},
        messages=[
            {
                "role": "system",
                "content": f"""
Tu es un expert en analyse sonore industrielle et historique.
Contexte général : {context}
Mission : Fournis une description précise des sons entendus,
identifie les activités en arrière-plan et nomme l'outil ou la machine.
Répond impérativement en français.
"""
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
            },
        ]
    )

    return completion.choices[0].message.audio.transcript
