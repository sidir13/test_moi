---
name: text-to-speech-with-instructions
description: Convert text into expressive speech while following detailed voice instructions.
---

# Text To Speech With Instructions

## Instructions
1. Assure-toi que les consignes vocales souhaitées sont enregistrées via `edit_voice_instructions`. Tu ne passes plus de paramètre `instructions` ici.
2. Si le texte provient d’un scénario structuré en plusieurs sections (`texte_narration_1`, `_2`, etc.), fusionne-les dans un seul champ `text` (sauf demande explicite de fichiers séparés). L’objectif est d’obtenir une narration continue.
3. Fournis `text` et, si besoin, `project_name`, `language` ou `output_path`.
4. Appelle `text_to_speech_with_instructions` : il lira automatiquement `voice_instructions` depuis `data/projects/<projet>/config.json` (créé lors de la sélection du projet, par défaut “Mémoire des Territoires”).
5. Confirme ensuite le fichier généré et rappelle la voix appliquée.

## Examples

**Example 1**
User: « Peux-tu créer un message d'accueil chaleureux pour mon musée ? (voix déjà enregistrée) »
```
[Call text_to_speech_with_instructions with
 text="Bonjour et bienvenue..."]
```
Response:
```
J'ai généré l'audio demandé et suivi les consignes de voix.
Fichier : data/generated_speech/tts_voix-feminine-40-ans_20260126T153210Z.wav
```

**Example 2**
User: « Utilise la voix définie pour “Projet Bretagne” et sauve dans data/tts/demo.wav »
```
[Call text_to_speech_with_instructions with
 text="In 1958, the yard started...",
 project_name="Projet Bretagne",
 language="English",
 output_path="data/tts/demo.wav"]
```

## Tool Details
- Function: `text_to_speech_with_instructions(text: str, project_name: Optional[str] = None, language: str = "French", output_path: Optional[str] = None) -> dict`
- Action: Generates a WAV file that matches the requested vocal style.
- Location: `src/memoiredesterritoires/text_to_speech_with_instructions/text_to_speech_with_instructions.py`
