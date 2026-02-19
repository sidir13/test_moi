---
name: generate-voice-instructions
description: Génère automatiquement des consignes vocales en anglais à partir d’un scénario, puis les enregistre dans `data/projects/<nom>/config.json`.
---

## Instructions
1. Demande toujours le texte/scénario décrivant l’ambiance ou l’époque à restituer.
2. Optionnel : récupère `project_name` et `hint_language` si l’utilisateur le mentionne.
3. Appelle `generate_voice_instructions` avec ces paramètres.
4. Confirme le projet mis à jour et rappelle que la synthèse TTS utilisera désormais ces consignes.

## Exemples

**Exemple 1**
```
[Call generate_voice_instructions with
 scenario="Au milieu du XVIIIe siècle, Nantes...",
 project_name="Mémoire des Territoires"]
```

**Exemple 2**
```
[Call generate_voice_instructions with
 scenario="Portrait sonore des ateliers de Penhoët dans les années 1950",
 project_name="Archives de Brest",
 hint_language="French"]
```

## Tool Details
- Function: `generate_voice_instructions(scenario: str, project_name: Optional[str] = None, hint_language: str = "French") -> dict`
- Action: Interroge un LLM pour créer des consignes vocales cohérentes avec le scénario et les persiste dans `data/projects/<projet>/config.json`.
- Location: `src/memoiredesterritoires/voice_instructions/generate_voice_instructions.py`
