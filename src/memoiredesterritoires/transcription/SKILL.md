---
name: transcribe-audio-openrouter
description: Explique comment une fonction Python découpe un fichier audio WAV en segments de 30 secondes, envoie chaque segment à un modèle de reconnaissance vocale via l’API OpenRouter (Gemini), puis reconstruit une transcription complète avec timestamps, **sans jamais s’arrêter avant la fin du fichier**.
---

Quand tu expliques ce code, tu dois toujours :

1. **Commencer par une analogie**  
   Comparer la fonction à un archiviste qui prend une bande magnétique complète, la découpe en cassettes de 30 secondes, les fait écouter à un expert humain **jusqu’à la toute dernière seconde**, puis recolle les comptes-rendus dans l’ordre.

2. **Dessiner un schéma**  
   Utiliser de l’ASCII art pour montrer :

   WAV original (entier)  
        ↓  
   Découpage 30s (pydub, jusqu’à la fin)  
        ↓  
   Encodage base64  
        ↓  
   OpenRouter / Gemini  
        ↓  
   Texte par chunk  
        ↓  
   Fusion finale (`join`)

3. **Parcourir le code pas à pas**  
Expliquer clairement :

- Le rôle de `AudioSegment.from_wav` (lecture et manipulation du signal)
- Le fait qu’on **ne tronque jamais** l’audio (pas de limite artificielle)
- La logique de découpage fixe en fenêtres temporelles couvrant **100% du fichier**
- Le passage binaire → base64 (transport API)
- La structure du prompt système (contrôle strict du style de sortie)
- Le mécanisme `client.chat.completions.create`
- L’agrégation finale avec `full_transcript.append` et `join`

4. **Mettre en avant les pièges (gotchas)**  
Mentionner systématiquement :

- Les chunks coupent parfois une phrase en deux (pas de VAD)
- Les timestamps sont relatifs au chunk, pas à l’audio global
- Le coût API augmente linéairement avec la durée totale
- La latence est strictement séquentielle (pas de parallélisme)
- Sur des fichiers longs (1h+), le risque d’échec en milieu de traitement
- La qualité dépend du modèle multimodal choisi

Ton :  
Pédagogique, orienté traitement du signal, LLM multimodaux et pipelines d’archivage audio.  
Utiliser des métaphores liées aux bandes magnétiques, aux archivistes, aux centres de transcription.  
Toujours structurer en sections claires (analogie, schéma, pas-à-pas, pièges).

## Tool Details
Function: `transcribe_audio(path: str, chunk_duration_s: int = 30, model: str = "google/gemini-3-flash-preview") -> str`  
Action: Découpe un fichier audio **en entier**, envoie chaque segment à OpenRouter, retourne la transcription complète **jusqu’à la dernière seconde du WAV**.  
Location: `src/memoiredesterritoires/transcription/transcription.py`
