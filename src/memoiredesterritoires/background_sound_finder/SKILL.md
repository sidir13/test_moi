---
name: find-background-sounds
description: Liste les fichiers disponibles dans `data/audio/background_sounds` et aide à choisir un bruit d'ambiance.
---

## Instructions
1. Si l'utilisateur mentionne un bruit ou une ambiance, passe ce terme comme `keyword` pour filtrer les dossiers.
2. Appelle `find_background_sounds` (tu peux préciser `limit` si l'utilisateur veut plusieurs exemples).
3. Retourne les chemins relatifs fournis (`data/audio/background_sounds/...`).
4. Invite ensuite l'utilisateur à sélectionner l'un des fichiers listés pour les prochaines étapes (mixage, etc.).

## Exemples

**Exemple 1**
```
[Call find_background_sounds with keyword="meule"]
```

**Exemple 2**
```
[Call find_background_sounds with keyword="chantier", limit=10]
```

## Tool Details
- Function: `find_background_sounds(keyword: Optional[str] = None, limit: int = 20) -> dict`
- Action: Explore `data/audio/background_sounds` et fournit des chemins audio filtrés.
- Location: `src/memoiredesterritoires/background_sound_finder/background_sound_finder.py`
