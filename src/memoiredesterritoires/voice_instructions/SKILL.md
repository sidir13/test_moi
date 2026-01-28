---
name: edit_voice_instructions
description: Modifie les consignes vocales (voice_instructions) pour un projet donné dans config.json.
---

# Modifier les consignes vocales

## Instructions
1. Identifie le projet concerné. Si l’utilisateur ne précise rien, utilise “Mémoire des Territoires”.
2. Reprends EXACTEMENT la demande de voix (sans l’enrichir) :
   - Si l’utilisateur parle dans une autre langue, reformule-la en français tout en conservant chaque nuance demandée.
   - Ne rajoute pas de descriptions supplémentaires.
3. Appelle `edit_voice_instructions` en fournissant :
   - `project_name` (facultatif si par défaut)
   - `voice_instructions` (obligatoire, en français et fidèle aux mots de l’utilisateur)
4. Confirme à l’utilisateur que les consignes ont été enregistrées et rappelle le chemin `config.json`.

## Exemples

**Exemple 1**
```
[Appel edit_voice_instructions avec
 project_name="Mémoire des Territoires",
 voice_instructions="Voix féminine 50 ans, ton posé, diction claire"]
```
Réponse :
```
Les consignes vocales ont été mises à jour pour “Mémoire des Territoires”.
```

**Exemple 2**
```
[Appel edit_voice_instructions avec
 project_name="Archives de Lyon",
 voice_instructions="Voix masculine jeune, rythme dynamique"]
```

## Détails du Tool
- Fonction : `edit_voice_instructions(project_name: Optional[str], voice_instructions: str) -> dict`
- Action : Met à jour/ajoute l’entrée `voice_instructions` dans `config.json`.
- Emplacement : `src/memoiredesterritoires/voice_instructions/edit_voice_instructions.py`
