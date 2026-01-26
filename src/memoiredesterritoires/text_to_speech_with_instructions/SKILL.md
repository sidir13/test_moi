---
name: text-to-speech-with-instructions
description: Convert text into expressive speech while following detailed voice instructions.
---

# Text To Speech With Instructions

## Instructions
1. Collect the exact script to read (`text`) and the stylistic directives (`instructions`). Do not proceed if either is missing.
2. Optionally note the language (default French) or a target filename if the user provides one.
3. Call the `text_to_speech_with_instructions` tool with:
   - `text`
   - `instructions`
   - optional `language`
   - optional `output_path`
4. Once the tool returns the WAV path, confirm generation and describe how the voice was adapted to the instructions.

## Examples

**Example 1**
User: « Peux-tu créer un message d'accueil chaleureux pour mon musée ? Voix de femme 40 ans, douce mais énergique. »
```
[Call text_to_speech_with_instructions with
 text="Bonjour et bienvenue...",
 instructions="Voix féminine 40 ans, douce, énergie positive"]
```
Response:
```
J'ai généré l'audio demandé et suivi les consignes de voix.
Fichier : data/generated_speech/tts_voix-feminine-40-ans_20260126T153210Z.wav
```

**Example 2**
User: « Lis ce paragraphe en anglais avec une diction posée, voix masculine grave. Sauvegarde sous data/tts/demo.wav »
```
[Call text_to_speech_with_instructions with
 text="In 1958, the yard started...",
 instructions="Voix masculine, grave, débit lent",
 language="English",
 output_path="data/tts/demo.wav"]
```

## Tool Details
- Function: `text_to_speech_with_instructions(text: str, instructions: str, language: str = "French", output_path: Optional[str] = None) -> dict`
- Action: Generates a WAV file that matches the requested vocal style.
- Location: `src/memoiredesterritoires/text_to_speech_with_instructions/text_to_speech_with_instructions.py`
