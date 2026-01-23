---
name: transcribe-audio-chunks
description: Explique comment un script Python utilise Faster-Whisper pour transcrire un entretien audio et regrouper automatiquement la transcription en blocs temporels de 30 secondes. À utiliser quand l’utilisateur demande comment fonctionne son code de transcription.
---

Quand tu expliques ce code, tu dois toujours :

1. **Commencer par une analogie**  
   Comparer le script à un stagiaire qui écoute une interview et rédige un compte-rendu par tranches de temps.

2. **Dessiner un schéma**  
   Utiliser de l’ASCII art pour montrer :
   - Fichier WAV → Faster-Whisper → Segments (start/end/text) → Regroupement 30s → Affichage

3. **Parcourir le code pas à pas**  
   Expliquer clairement :
   - Le chargement du modèle (`large-v3-turbo`, CPU, int8)  
   - Le rôle du VAD (Voice Activity Detection)  
   - La structure des objets `segment`  
   - La logique des checkpoints temporels (30s, 60s, etc.)  
   - La reconstruction du texte avec `join()`

4. **Mettre en avant les pièges (gotchas)**  
   Mentionner systématiquement :
   - Les chunks ne sont pas exactement de 30s (dépend des segments)  
   - Le VAD peut supprimer des sons faibles  
   - Les performances CPU vs GPU  

Ton :  
Pédagogique, orienté traitement du signal et archivage audio.  
Utiliser des métaphores liées aux interviews, aux archives, à la transcription.  
Toujours structurer en sections claires (analogie, schéma, pas-à-pas, pièges).

## Tool Details
Function: transcribe_chunks(path: str,max_time=180, chunk_size=30) -> str
Action: transcript the audio
Location: src/memoiredesterritoires/transcription/transcription.py