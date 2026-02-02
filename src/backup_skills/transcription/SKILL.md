---
name: transcription
description: Transcrire les archives audio en fenêtres successives (par défaut 20 minutes) jusqu’à couvrir tout le fichier.
---

# Transcription séquencée

## Instructions
1. Identifie le besoin (ex. « transcrire tout le fichier ») et initialise `start_time=0`.
2. Choisis un `max_time` adapté (par défaut 1200 secondes = 20 minutes). Ajuste si l’utilisateur demande une autre granularité.
3. Appelle `transcribe_chunks` avec :
   - `path`
   - `start_time`
   - `max_time`
   - éventuellement `chunk_size` (ex. 30 secondes pour regrouper les segments)
4. Lis la réponse :
   - `chunks` contient les blocs transcrits avec `chunk_start`/`chunk_end`.
   - `has_more` + `next_start_time` indiquent s’il faut relancer l’outil.
5. Tant que `has_more` est `true`, rappelle `transcribe_chunks` en mettant `start_time=next_start_time` afin de couvrir la suite du fichier.
6. Lorsque `has_more` devient `false`, assemble ou résume l’ensemble des chunks pour répondre à l’utilisateur.

## Examples

**Exemple 1 — Fichier complet en plusieurs appels**
```
[Call transcribe_chunks with path="data/eng/int/Gilles.WAV", start_time=0, max_time=1200]
→ has_more = true, next_start_time = 119.8
[Call transcribe_chunks with path="data/eng/int/Gilles.WAV", start_time=119.8, max_time=1200]
→ has_more = false (transcription terminée)
```

**Exemple 2 — Fenêtre unique**
```
[Call transcribe_chunks with path="data/audio/sample.wav",
 start_time=0,
 max_time=300,
 chunk_size=60]
```

## Tool Details
- Function: `transcribe_chunks(path: str, start_time: float = 0.0, max_time: int = 180, chunk_size: int = 30) -> dict`
- Action: Transcrit jusqu’à `max_time` secondes en partant de `start_time`, renvoie les chunks + indicateurs pour l’appel suivant.
- Location: `src/memoiredesterritoires/transcription/transcription.py`
