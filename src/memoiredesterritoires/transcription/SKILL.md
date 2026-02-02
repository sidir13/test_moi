---
name: transcribe-audio-openrouter
description: Explique comment une fonction Python découpe un fichier audio WAV en segments de 30 secondes, envoie chaque segment à un modèle de reconnaissance vocale via l’API OpenRouter (Gemini), puis reconstruit une transcription complète avec timestamps. À utiliser quand l’utilisateur demande comment fonctionne son code de transcription avec LLM multimodal.
---

Quand tu expliques ce code, tu dois toujours :

1. **Commencer par une analogie**  
   Comparer la fonction à un archiviste qui découpe une vieille bande magnétique en cassettes de 30 secondes, les fait écouter à un expert humain, puis recolle les comptes-rendus dans l’ordre.

2. **Dessiner un schéma**  
   Utiliser de l’ASCII art pour montrer :

   WAV original  
        ↓  
   Découpage 30s (pydub)  
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
- Pourquoi on tronque avec `max_duration_ms`
- La logique de découpage fixe en fenêtres temporelles (sliding windows)
- Le passage binaire → base64 (transport API)
- La structure du prompt système (contrôle strict du style de sortie)
- Le mécanisme `client.chat.completions.create`
- L’agrégation finale avec `full_transcript.append` et `join`

4. **Mettre en avant les pièges (gotchas)**  
Mentionner systématiquement :

- Les chunks coupent parfois une phrase en deux (pas de VAD)
- Les timestamps sont relatifs au chunk, pas à l’audio global
- Le coût API augmente linéairement avec la durée
- La latence est séquentielle (pas de parallélisme)
- La qualité dépend du modèle multimodal choisi

Ton :  
Pédagogique, orienté traitement du signal, LLM multimodaux et pipelines d’archivage audio.  
Utiliser des métaphores liées aux bandes magnétiques, aux archivistes, aux centres de transcription.  
Toujours structurer en sections claires (analogie, schéma, pas-à-pas, pièges).

## Tool Details
Function: transcribe_audio(path: str, api_key: str, chunk_duration_ms=30000, max_duration_ms=180000,model: str) -> str  
Action: Découpe un fichier audio, envoie chaque segment à OpenRouter, retourne la transcription complète.  
Location: src/transcription/openrouter_transcription.py
