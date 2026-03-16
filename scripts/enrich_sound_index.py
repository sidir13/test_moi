"""
Enrichissement de data/audio/background_sounds/index.json
par analyse audio réelle via Gemini multimodal.

Pour chaque son :
  1. Chargement mono 16 kHz (librosa)
  2. Suppression des silences
  3. Sélection du chunk de 5 s le plus énergique (RMS)
  4. Envoi à Gemini Flash → retour JSON {description, tags, mood, intensity, activity}
  5. Mise à jour de l'entrée dans index.json

Usage :
    python scripts/enrich_sound_index.py
    python scripts/enrich_sound_index.py --force   # re-analyse même les sons déjà enrichis
"""

import sys
import os
import json
import base64
import io
import time
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import librosa
import soundfile as sf
from openai import OpenAI
from dotenv import load_dotenv

# ── Chemins ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "data" / "audio" / "background_sounds" / "index.json"

# ── Config analyse ──────────────────────────────────────────────────────────
CHUNK_DURATION  = 5.0       # secondes envoyées à Gemini
ENERGY_THRESHOLD = 0.005    # seuil RMS minimum (silence)
SAMPLE_RATE     = 16000     # Hz pour le rééchantillonnage
MODEL           = "google/gemini-2.0-flash-001"
DELAY_BETWEEN   = 1.5       # secondes entre chaque appel API

# ── Prompt système ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Tu es un expert en analyse sonore industrielle et historique, spécialisé dans les archives des chantiers navals français des années 1960-1980 (Nantes, Saint-Nazaire).

Après écoute du son, réponds UNIQUEMENT avec un objet JSON valide, sans markdown, sans explication, avec exactement ces clés :

{
  "description": "Description précise en français (2-3 phrases) : quels sons on entend, quel outil ou machine, quel type d'activité, quelle ambiance. Sois spécifique.",
  "tags": ["liste", "de", "5", "à", "12", "mots-clés", "en_minuscules_avec_tirets"],
  "mood": "un parmi : busy / calm / intense / rhythmic / mechanical / atmospheric",
  "intensity": "un parmi : low / medium / high",
  "activity": "nom_court_de_l_activite_en_snake_case"
}"""

USER_PROMPT = "Analyse ce son d'ambiance industrielle issu d'archives de chantiers navals. Identifie précisément l'outil, la machine ou l'activité."


def get_best_chunk_b64(audio_path: str) -> tuple[str, float, float]:
    """Extrait le chunk de 5 s le plus énergique et le retourne en base64 WAV."""
    y, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
    y, _ = librosa.effects.trim(y, top_db=30)

    chunk_size = int(CHUNK_DURATION * sr)

    if len(y) < chunk_size:
        # Fichier plus court que le chunk → on prend tout
        chunk = y
        start, end = 0.0, len(y) / sr
    else:
        rms = librosa.feature.rms(y=y, frame_length=chunk_size, hop_length=chunk_size)[0]
        best_idx = int(np.argmax(rms))
        best_energy = float(rms[best_idx])

        if best_energy < ENERGY_THRESHOLD:
            raise ValueError("Énergie trop faible — fichier silencieux ?")

        i = best_idx * chunk_size
        chunk = y[i : i + chunk_size]
        start = i / sr
        end = (i + len(chunk)) / sr

    buf = io.BytesIO()
    sf.write(buf, chunk, sr, format="WAV")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    return b64, round(start, 2), round(end, 2)


def analyse_with_gemini(client: OpenAI, b64_audio: str) -> dict:
    """Envoie le chunk à Gemini et retourne le JSON parsé."""
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {
                        "type": "input_audio",
                        "input_audio": {"data": b64_audio, "format": "wav"},
                    },
                ],
            },
        ],
    )
    raw = completion.choices[0].message.content.strip()

    # Nettoyage éventuel de balises markdown
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


def enrich_sound(sound: dict, client: OpenAI, force: bool) -> dict:
    """Enrichit une entrée son et retourne l'entrée mise à jour."""
    # Déjà enrichi par IA ?
    if not force and sound.get("ai_enriched"):
        print(f"  >>  Deja enrichi -- ignore (--force pour re-analyser)")
        return sound

    audio_path = ROOT / sound["file"]
    if not audio_path.exists():
        print(f"  [SKIP]  Fichier introuvable : {audio_path}")
        return sound

    try:
        b64, start, end = get_best_chunk_b64(str(audio_path))
        print(f"     Chunk selectionne : {start:.1f}s -> {end:.1f}s")

        result = analyse_with_gemini(client, b64)

        # Fusion avec les données existantes
        sound["tags"] = result.get("tags", sound.get("tags", []))
        sound["metadata"]["description"] = result.get("description", sound["metadata"].get("description", ""))
        sound["metadata"]["mood"]        = result.get("mood",        sound["metadata"].get("mood", ""))
        sound["metadata"]["intensity"]   = result.get("intensity",   sound["metadata"].get("intensity", ""))
        sound["metadata"]["activity"]    = result.get("activity",    sound["metadata"].get("activity", ""))
        sound["ai_enriched"]             = True
        sound["ai_chunk_analyzed"]       = {"start_s": start, "end_s": end}

        print(f"  [OK]  {result.get('description', '')[:80]}...")
        return sound

    except json.JSONDecodeError as e:
        print(f"  [ERR]  JSON invalide recu de Gemini : {e}")
        return sound
    except Exception as e:
        print(f"  [ERR]  Erreur : {e}")
        return sound


def main():
    parser = argparse.ArgumentParser(description="Enrichit index.json par analyse audio Gemini")
    parser.add_argument("--force", action="store_true", help="Re-analyse même les sons déjà enrichis")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        sys.exit("Clé ANTHROPIC_AUTH_TOKEN manquante dans .env")

    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    with open(INDEX_PATH, encoding="utf-8") as f:
        index = json.load(f)

    sounds = index.get("sounds", [])
    total  = len(sounds)
    print(f"\n{'='*55}")
    print(f"  Enrichissement de {total} sons via Gemini multimodal")
    print(f"  Modèle : {MODEL}")
    print(f"  Chunk  : {CHUNK_DURATION}s (segment le plus énergique)")
    print(f"{'='*55}\n")

    for i, sound in enumerate(sounds, 1):
        label = sound.get("filename", sound.get("file", "?"))
        cat   = sound.get("category", "")
        print(f"[{i}/{total}] {cat} / {label}")
        sounds[i - 1] = enrich_sound(sound, client, force=args.force)

        if i < total:
            time.sleep(DELAY_BETWEEN)

    index["sounds"]       = sounds
    index["last_updated"] = datetime.now().isoformat()

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    enriched = sum(1 for s in sounds if s.get("ai_enriched"))
    print(f"\n{'='*55}")
    print(f"  Termine : {enriched}/{total} sons enrichis")
    print(f"  Fichier mis à jour : {INDEX_PATH}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
