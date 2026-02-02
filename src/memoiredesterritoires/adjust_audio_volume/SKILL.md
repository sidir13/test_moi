---
name: adjust-audio-volume
description: Ajuste le volume perçu d’un fichier audio en appliquant un gain logarithmique et sauvegarde le résultat.
---

# Ajuster le volume audio

## Instructions
1. Récupère le chemin du fichier source (`input_file`). C’est obligatoire.
2. Propose éventuellement un `output_file` (par défaut `data/generated_speech/output.wav`) et un pourcentage (`volume_percent`, 10–300).
3. Appelle `adjust_audio_volume` avec les paramètres souhaités.
4. Vérifie la réponse : elle indique le niveau RMS avant/après, le gain en dB et le chemin du fichier sauvegardé. Informe l’utilisateur et mentionne si une saturation est détectée.

## Exemples

**Exemple 1**
```
[Call adjust_audio_volume with
 input_file="data/audio/original.wav"]
```

**Exemple 2**
```
[Call adjust_audio_volume with
 input_file="data/audio/interview.wav",
 output_file="data/audio/interview_quiet.wav",
 volume_percent=80]
```

## Tool Details
- Function: `adjust_audio_volume(input_file: Path, output_file: Path | str = "data/generated_speech/output.wav", volume_percent: float = 90) -> dict`
- Action: Calcule le gain nécessaire (logarithmique), ajuste l’amplitude et écrit un nouveau fichier WAV avec les métadonnées de mesure.
- Location: `src/memoiredesterritoires/adjust_audio_volume/adjust_audio_volume.py`
