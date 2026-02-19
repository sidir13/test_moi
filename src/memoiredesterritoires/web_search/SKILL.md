---
name: restricted-web-search
description: Effectue une recherche web limitée aux domaines autorisés stockés dans `data/projects/<nom>/config.json` pour un projet donné.
---

# Recherche Web Restreinte

## Instructions
1. Détermine le projet ciblé (par défaut “Mémoire des Territoires” si rien n’est précisé).
2. Vérifie qu’une requête précise (`query`) est fournie.
3. Appelle `restricted_web_search` avec :
   - `query`
   - `project_name` (facultatif)
   - éventuellement `max_results` ou `model` si l’utilisateur l’exige
4. Résume la réponse en citant uniquement les domaines autorisés. Signale si aucune information n’est disponible dans les sites autorisés.

## Exemples

**Exemple 1**
```
[Call restricted_web_search with
 project_name="Mémoire des Territoires",
 query="Histoire du chantier naval de Saint-Nazaire"]
```

**Exemple 2**
```
[Call restricted_web_search with
 project_name="Archives de Lyon",
 query="Biographie de Jeanne Joubert",
 max_results=3]
```

## Détails du Tool
- Fonction : `restricted_web_search(query: str, project_name: Optional[str] = None, model: str = "google/gemini-3-pro-preview", max_results: int = 5) -> dict`
- Action : Lance une requête OpenRouter avec plugin web limité aux domaines autorisés pour le projet.
- Emplacement : `src/memoiredesterritoires/web_search/restricted_web_search.py`
