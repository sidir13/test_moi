---
name: mix-voice-with-noise
description: Superpose un bruit d’ambiance sur une voix avec contrôle du SNR et exporte le mixage final.
---

## Instructions
1. Collecte sans ambiguïté le chemin du fichier voix (`voice_file`) et celui du bruit (`noise_file`). Refuse si un des deux manque.
2. Demande les paramètres optionnels si l’utilisateur les mentionne (SNR en dB, position de départ du bruit, durée, décalage dans le fichier bruit).
3. Appelle `mix_voice_with_noise` avec ces paramètres.
4. Annonce le chemin de sortie, le SNR final et rappelle toute saturation signalée par l’outil.

## Exemples

**Exemple 1**
```
[Call mix_voice_with_noise with
 voice_file="data/voice/dessinateur.wav",
 noise_file="data/audio/background_sounds/Meule/AV-1-S-OUT-201-1-A.wav"]
```

**Exemple 2**
```
[Call mix_voice_with_noise with
 voice_file="data/voice/interview.wav",
 noise_file="data/audio/background_sounds/Soudeur/AV-1-S-MET-502.wav",
 output_file="data/mixes/interview_forge.wav",
 snr_db=10,
 start_time=5,
 noise_duration=12,
 noise_start_offset=1]
```

## Tool Details
- Function: `mix_voice_with_noise(voice_file: Path | str, noise_file: Path | str, output_file: Path | str = "data/generated_speech/mixed_output.wav", snr_db: float = 15, start_time: float = 0, noise_duration: float | None = 3, noise_start_offset: float = 2) -> dict`
- Action: Ajuste le niveau du bruit pour atteindre le SNR souhaité, le boucle si nécessaire, mixe à l’instant demandé et sauvegarde le résultat.
- Location: `src/memoiredesterritoires/insert_background_sounds/insert_backgrounds_sounds.py`
