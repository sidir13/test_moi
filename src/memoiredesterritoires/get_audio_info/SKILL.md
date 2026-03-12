---
name: get-info-tools
description: Outils d'analyse et de découverte audio. Permet d'obtenir les métadonnées techniques d'un fichier audio et de rechercher des sons disponibles dans la bibliothèque. Ces outils ne modifient aucun fichier — ils retournent uniquement de l'information.
---


# Outils d'analyse et de découverte audio


## Instructions
1. Utilise `get_audio_info` dès que tu as besoin de connaître la durée, le niveau RMS ou le SNR d'un fichier avant tout mixage.
2. Utilise `find_background_sounds` pour rechercher un fichier son par mot-clé avant d'appeler un outil de mixage.
3. Ces deux outils peuvent être appelés dans n'importe quel ordre, et autant de fois que nécessaire.
4. Transmets les résultats (durée, RMS, chemins de fichiers) aux outils de mixage (voir SKILL `audio-tools`).


## Outil 1 : get_audio_info

Analyse un fichier audio et retourne ses métadonnées techniques.

**Paramètres**
- `audio_file` *(obligatoire)* : chemin du fichier audio à analyser

**Ce que retourne l'outil**
- `duration_s` : durée en secondes → définit la plage valide des timestamps pour le mixage
- `rms_db` : niveau RMS moyen → référence pour calibrer le SNR des sons à insérer
- `peak_db` : pic d'amplitude → indique si le fichier est proche de la saturation
- `snr_estimate_db` : estimation du rapport signal/bruit → qualité de l'enregistrement
- `sample_rate` : fréquence d'échantillonnage → les sons insérés seront resampleés sur cette valeur

**Exemples**

Quand l'utilisateur veut savoir combien de temps dure un fichier voix :
- `audio_file` = `"data/audio/narration.wav"`

Quand l'utilisateur veut connaître le niveau sonore d'un fond avant de le mixer :
- `audio_file` = `"data/audio/background_sounds/mer/vagues.wav"`


## Outil 2 : find_background_sounds

Recherche les fichiers sons disponibles dans la bibliothèque, avec filtre optionnel par mot-clé.

**Paramètres**
- `keyword` *(optionnel)* : mot-clé pour filtrer par nom de dossier (ex: `"mer"`, `"forge"`, `"port"`)
- `limit` *(optionnel)* : nombre maximum de résultats (défaut : `20`)

**Ce que retourne l'outil**
- `files` : liste des chemins relatifs des fichiers trouvés → à passer directement aux outils de mixage
- `count` : nombre de résultats trouvés

**Exemples**

Quand l'utilisateur veut trouver des sons de forge pour illustrer une scène d'atelier :
- `keyword` = `"forge"`

Quand l'utilisateur veut voir tous les sons disponibles :
- `keyword` = `null`
- `limit` = `20`

Quand l'utilisateur cherche une ambiance maritime :
- `keyword` = `"mer"`


## Tool Details
- Function 1: `get_audio_info(audio_file: Path | str) -> dict`
- Function 2: `find_background_sounds(keyword: Optional[str] = None, limit: int = 20) -> dict`
- Location: `src/memoiredesterritoires/audio/get_info_tools.py`
