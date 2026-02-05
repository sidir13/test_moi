---
name: rank-scenarios
description: Analyse un fichier config JSON et re-classe les scénarios associés selon leur adéquation aux instructions, puis met à jour la config.
---

## Instructions
1. Demander le chemin du `config_path` (ex: `data/scenarios/.../config_xxx.json`) et du dossier `scenarios_dir` contenant les scénarios.
2. Vérifier que le projet est bien celui dont on veut actualiser l’ordre.
3. Appeler `rank_scenarios_against_config` avec ces chemins. L’outil lit les scénarios et confie au LLM le soin de les classer.
4. Annoncer l’ordre obtenu et préciser que la clé `scenario_ranking` a été enregistrée dans le fichier config.

## Exemples

**Exemple 1**
```
[Call rank_scenarios_against_config with
 config_path="data/scenarios/chantiers_navals/scenarios/config_20260204_172233.json",
 scenarios_dir="data/scenarios/chantiers_navals/scenarios"]
```

## Tool Details
- Function: `rank_scenarios_against_config(config_path: str, scenarios_dir: str, project_name: Optional[str] = None) -> dict`
- Action: Charge config + scénarios, demande à l’LLM de sortir un classement, l’écrit dans `scenario_ranking` et retourne la liste.
- Location: `src/memoiredesterritoires/scenario_ranking/rank_scenarios.py`
