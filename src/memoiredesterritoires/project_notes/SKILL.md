---
name: update-project-notes
description: Ajoute ou met à jour les notes générales d’un projet (brief utilisateur) dans config.json.
---

## Instructions
1. Demande à l’utilisateur les informations qu’il veut conserver (objectifs, contraintes, ambiance, voix souhaitée, etc.).
2. Identifie le projet (`project_name`). Si rien n’est précisé, utilise “Mémoire des Territoires”.
3. Appelle `update_project_notes` avec ce texte. Ces notes seront relues par les autres skills.
4. Confirme le projet et rappelle que les notes sont sauvegardées dans `config.json`.

## Exemple
```
[Call update_project_notes with
 project_name="La Vie de Gilles",
 description="Histoires de 1 minute mettant en valeur le parcours de Gilles... voix féminine professeur." ]
```

## Tool Details
- Function: `update_project_notes(project_name: Optional[str], description: str) -> dict`
- Action: Stocke le brief utilisateur sous la clé `project_notes` du projet.
- Location: `src/memoiredesterritoires/project_notes/update_project_notes.py`
