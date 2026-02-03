import os
from elevenlabs import ElevenLabs
from dotenv import load_dotenv
# À adapter : renseigner ta clé API ELEVENLABS_API_KEY (variable d'environnement)

load_dotenv()
api_key = os.getenv("ELEVENLABS_API_KEY")

client = ElevenLabs(api_key=api_key)


# Exemple minimal de génération TTS et sauvegarde dans un fichier MP3

text = """Imaginez la Loire en 1950. Les chantiers navals de Nantes bourdonnaient d'activité.
Des coques immenses prenaient forme sous les mains expertes des soudeurs et des charpentiers."""


# PAID VOICES
# 5jCmrHdxbpU36l1wb3Ke txtf1EDouKke753vN8SL fnoOtHjtLbYs6mOpUSdr
# x10MLxaAmShMYt7vs7pl hv6gVog5LgtIUX88Nmq8 ohItIVrXTBI80RrUECOD
# 0bKGtCCpdKSI5NjGhU3z 2AGrjHJgmTgUqzy68M9W cuo3D4C6LVenyV7b2Kpd
# b40q94MErxP9aasHjJ2w cuo3D4C6LVenyV7b2Kpd EMuO6fFLrXKOryHzij6K
# TTtB1x9U8PF0Vgf20IAP rgFgMEXfdGwXCYio7I0J aQROLel5sQbj1vuIVi6B
# GgV5QStPLpmkN7FOHJtY I0ZNjxaJrLklKmZK1mlA TojRWZatQyy9dujEdiQ1
# jK7dAsiVAhbApIS8KkWB NOpBlnGInO9m6vDvFkFC 5l4ttmr4SKNgi0HnOelT
# 6vTyAgAT8PncODBcLjRf

# Free Voices
# JBFqnCBsd6RMkjVDRZzb pqHfZKP75CvOlQylNhV4

voice_id = "pqHfZKP75CvOlQylNhV4"  # Remplace par l'ID d'une voix de ta librairie



# Appel type (adapté au client officiel actuel)
# audio = client.text_to_speech.convert(
#     voice_id=voice_id,
#     model_id="eleven_multilingual_v2",  # ou "eleven_flash_v2_5", "eleven_turbo_v2_5", etc.  
#     text=text,
#     output_format="mp3_44100_128"       # MP3 44.1 kHz, 128 kbps (voir section formats)  
# )


# with open("output_simple_tts.mp3", "wb") as f:
#     for chunk in audio:
#         f.write(chunk)

texts_emotion = {
    "neutre": "Elle dit qu'elle est prête à commencer la présentation.",
    "enthousiaste": "Elle dit avec beaucoup d'enthousiasme qu'elle est prête à commencer la présentation !",
    "inquiète": "Elle dit, d'une voix inquiète, qu'elle n'est pas certaine d'être prête pour la présentation..."
}

for label, txt in texts_emotion.items():
    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        text=txt,
        output_format="mp3_44100_128"
    )
    filename = f"tts_emotion_{label}.mp3"

# # Sauvegarde sur disque
# with open("output_simple_tts.mp3", "wb") as f:
#     f.write(audio)
with open("emotion_output_tts.mp3", "wb") as f:
    for chunk in audio:
        f.write(chunk)

