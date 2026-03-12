---
name: audio-tools
description: Outils de traitement et de mixage audio. Ajuste le volume d'un fichier, insère des sons ponctuels à des timestamps précis avec contrôle SNR et fondus, ou ajoute un fond sonore continu. Appeler get-info-tools en premier pour obtenir durée et niveaux RMS avant tout mixage.
---


# Outils de mixage audio


## Instructions
1. Appelle toujours `get_audio_info` (SKILL `get-info-tools`) avant de mixer pour connaître la durée et le RMS de la voix.
2. Appelle `find_background_sounds` (SKILL `get-info-tools`) pour trouver les fichiers sons à utiliser.
3. Insère les sons ponctuels avec `mix_voice_with_noise` — chaîne les appels (output N → input N+1).
4. Termine TOUJOURS par `mix_voice_with_background` si un fond continu est souhaité.
5. Utilise `adjust_audio_volume` uniquement pour corriger le volume d'un fichier isolé.


## Ordre d'appel recommandé

```
get_audio_info          → connaître durée + RMS voix
find_background_sounds  → trouver les fichiers sons
mix_voice_with_noise    → insérer son 1 (t=Xs, durée Ys)
mix_voice_with_noise    → insérer son 2 sur l'output précédent
...
mix_voice_with_background → ajouter le fond continu en dernier
```


## Outil 1 : adjust_audio_volume

Ajuste le volume d'un fichier audio seul en décibels.

**Paramètres**
- `input_file` *(obligatoire)* : chemin du fichier d'entrée
- `output_file` *(optionnel)* : chemin de sortie (défaut : `data/generated_speech/output.wav`)
- `gain_db` *(optionnel)* : gain en dB (défaut : `0.0`)
  - `0 dB` = inchangé, `-3 dB` = moitié puissance, `+6 dB` = double amplitude

**Exemples**

Quand l'utilisateur veut baisser le volume d'une narration de 3 dB :
- `input_file` = `"data/audio/narration.wav"`
- `output_file` = `"data/audio/narration_quiet.wav"`
- `gain_db` = `-3.0`

Quand l'utilisateur veut amplifier un fichier trop faible :
- `input_file` = `"data/audio/voix.wav"`
- `gain_db` = `+6.0`


## Outil 2 : mix_voice_with_noise

Insère un son ponctuel à un timestamp précis sur une piste voix.
Applique automatiquement des fondus (logarithmic IN / exponential OUT par défaut).

**Paramètres**
- `voice_file` *(obligatoire)* : fichier voix de base (ou output de l'appel précédent)
- `noise_file` *(obligatoire)* : fichier son à insérer
- `output_file` *(optionnel)* : chemin de sortie (défaut : `data/generated_speech/mixed_output.wav`)
- `snr_db` *(optionnel)* : rapport signal/bruit en dB (défaut : `26.0`)
  - `26 dB` = voix très claire, `20 dB` = bruit perceptible, `15 dB` = bruit fort
- `start_time` *(optionnel)* : timestamp de départ du son en secondes (défaut : `0`)
- `noise_duration` *(optionnel)* : durée du son en secondes, `null` = jusqu'à la fin (défaut : `3`)
- `noise_start_offset` *(optionnel)* : point de départ dans le fichier son en secondes (défaut : `0`)
- `fade_in_s` *(optionnel)* : durée fade in en secondes (défaut : `0.3`)
- `fade_out_s` *(optionnel)* : durée fade out en secondes (défaut : `0.5`)
- `fade_in_type` *(optionnel)* : courbe fade in — `linear`, `logarithmic`, `exponential`, `equal_power`, `sigmoid` (défaut : `logarithmic`)
- `fade_out_type` *(optionnel)* : courbe fade out (défaut : `exponential`)

**Règle d'or des fondus**
- Sons courts / SFX : `fade_in_s=0.1-0.5`, courbes `logarithmic` / `exponential`
- Sons longs / ambiances : `fade_in_s=1.0-3.0`, courbes `logarithmic` / `exponential`

**Exemples**

Quand l'utilisateur veut insérer un bruit de meuleuse à t=5s pendant 4 secondes :
- `voice_file` = `"data/audio/narration.wav"`
- `noise_file` = `"data/audio/background_sounds/forge/meuleuse.wav"`
- `output_file` = `"data/audio/mix_step_1.wav"`
- `snr_db` = `15`
- `start_time` = `5.0`
- `noise_duration` = `4.0`
- `fade_in_s` = `2.0`, `fade_out_s` = `2.0`

Quand l'utilisateur veut chaîner un second son (port à t=20s) sur le résultat précédent :
- `voice_file` = `"data/audio/mix_step_1.wav"`
- `noise_file` = `"data/audio/background_sounds/port/ambiance.wav"`
- `output_file` = `"data/audio/mix_step_2.wav"`
- `snr_db` = `20`
- `start_time` = `20.0`
- `noise_duration` = `8.0`


## Outil 3 : mix_voice_with_background

Ajoute un fond sonore continu sur toute la durée de la voix.
Applique des fondus longs (sigmoid par défaut) pour un rendu cinématographique.
À appeler EN DERNIER, après tous les sons ponctuels.

**Paramètres**
- `voice_file` *(obligatoire)* : fichier voix (ou dernier output de mix_voice_with_noise)
- `background_file` *(obligatoire)* : fichier fond sonore
- `output_file` *(optionnel)* : chemin de sortie (défaut : `data/generated_speech/output_mix.wav`)
- `voice_bg_ratio_db` *(optionnel)* : écart dB voix/fond (défaut : `-20.0`)
  - `-17 dB` = ambiance légère, `-20 dB` = narration standard, `-26 dB` = très en retrait
- `fade_in_s` *(optionnel)* : durée fade in fond en secondes (défaut : `2.0`)
- `fade_out_s` *(optionnel)* : durée fade out fond en secondes (défaut : `2.0`)
- `fade_in_type` *(optionnel)* : courbe fade in (défaut : `logarithmic`)
- `fade_out_type` *(optionnel)* : courbe fade out (défaut : `exponential`)

**Exemples**

Quand l'utilisateur veut ajouter une ambiance maritime en fond sur toute la narration :
- `voice_file` = `"data/audio/mix_step_2.wav"`
- `background_file` = `"data/audio/background_sounds/mer/vagues.wav"`
- `output_file` = `"data/audio/final_mix.wav"`
- `voice_bg_ratio_db` = `-26.0`
- `fade_in_s` = `2.0`, `fade_out_s` = `2.0`
- `fade_in_type` = `"logarithmic"`, `fade_out_type` = `"exponential"`

Quand l'utilisateur veut un fond discret pour un podcast :
- `voice_file` = `"data/audio/narration.wav"`
- `background_file` = `"data/audio/background_sounds/ambiance/interieur.wav"`
- `voice_bg_ratio_db` = `-18.0`


## Tool Details
- Function 1: `adjust_audio_volume(input_file, output_file, gain_db) -> dict`
- Function 2: `mix_voice_with_noise(voice_file, noise_file, output_file, snr_db, start_time, noise_duration, noise_start_offset, fade_in_s, fade_out_s, fade_in_type, fade_out_type) -> dict`
- Function 3: `mix_voice_with_background(voice_file, background_file, output_file, voice_bg_ratio_db, fade_in_s, fade_out_s, fade_in_type, fade_out_type, start_time, end_offset) -> dict`
- Location: `src/memoiredesterritoires/audio/audio_tools.py`
