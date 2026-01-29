# Voice Persona Matcher

## Role

Matching de profils vocaux optimaux avec personas et tons narratifs.

## Model Configuration

- Model: claude-sonnet-4-5
- Temperature: 0.3
- Max tokens: 1000

## Functions

### match_voice_profile

Sélectionne profil vocal optimal pour une narration.

**Input** : `{"persona": dict, "tone": str, "age_period": str}`
**Output** : Profil vocal détaillé (genre, âge, accent, timbre, delivery)
