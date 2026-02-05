---
name: read-json
description: Ouvre un fichier JSON local et retourne son contenu, avec option pour extraire une clé spécifique.
---

## Instructions
1. Vérifie que l’utilisateur fournit un chemin valide sous le projet (ex. `data/...json`).
2. Si le fichier contient plusieurs projets (ex: `config.json`), utilise `project_name` pour cibler la bonne entrée.
3. Optionnel : passe `key` pour retourner uniquement la valeur souhaitée.
4. Appelle `read_json_file` avec `path`, `project_name`, `key`, puis restitue le contenu.

## Exemples

**Exemple 1**
```
[Call read_json_file with path="data/scenarios/scenario_1.json"]
```

**Exemple 2**
```
[Call read_json_file with path="data/scenarios/scenario_1.json", key="texte_narration"]
```

**Exemple 3**
```
[Call read_json_file with path="config.json", project_name="Mémoire des Territoires", key="voice_instructions"]
```

## Tool Details
- Function: `read_json_file(path: str, key: Optional[str] = None, project_name: Optional[str] = None) -> dict`
- Action: Charge un fichier JSON et renvoie soit l’objet complet, soit la valeur d’une clé.
- Location: `src/memoiredesterritoires/json_utils/read_json.py`
