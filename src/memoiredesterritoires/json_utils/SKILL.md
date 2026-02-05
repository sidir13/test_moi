---
name: read-json
description: Ouvre un fichier JSON local et retourne son contenu, avec option pour extraire une clé spécifique.
---

## Instructions
1. Vérifie que l’utilisateur fournit un chemin valide sous le projet (ex. `data/...json`).
2. Optionnel : si l’utilisateur ne veut qu’une partie, passe `key` pour retourner uniquement cette valeur.
3. Appelle `read_json_file` avec `path` (et `key`).
4. Réponds en résumant le contenu ou en mentionnant l’extrait retourné.

## Exemples

**Exemple 1**
```
[Call read_json_file with path="data/scenarios/scenario_1.json"]
```

**Exemple 2**
```
[Call read_json_file with path="data/scenarios/scenario_1.json", key="texte_narration"]
```

## Tool Details
- Function: `read_json_file(path: str, key: Optional[str] = None) -> dict`
- Action: Charge un fichier JSON et renvoie soit l’objet complet, soit la valeur d’une clé.
- Location: `src/memoiredesterritoires/json_utils/read_json.py`
