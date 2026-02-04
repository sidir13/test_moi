---
name: elevenlabs-tts
description: Utilise l’API ElevenLabs pour générer une narration quand l’utilisateur demande explicitement cette voix.
---

## Instructions
1. N’utilise ce skill que si l’utilisateur demande « ElevenLabs » ou une voix spécifique de cette plateforme.
2. Recueille le `text` à lire. Optionnel : `voice_id`, `model_id`, `output_path`.
3. Appelle `eleven_labs_tts` avec les paramètres nécessaires.
4. Retourne le chemin du fichier MP3 généré et rappelle la voix utilisée.

## Exemples

**Exemple 1**
```
[Call eleven_labs_tts with text="Bonjour" voice_id="pqHfZKP75CvOlQylNhV4"]
```

**Exemple 2**
```
[Call eleven_labs_tts with text="Narration", voice_id="custom123", output_path="data/tts/narration.mp3"]
```

## Tool Details
- Function: `eleven_labs_tts(text: str, voice_id: str = DEFAULT, output_path: Optional[str] = None, model_id: str = DEFAULT) -> dict`
- Action: Génère un fichier audio via ElevenLabs.
- Location: `src/memoiredesterritoires/elevenlabs_tts/elevenlabs_tts.py`
