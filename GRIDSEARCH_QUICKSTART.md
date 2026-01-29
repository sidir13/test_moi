# 🚀 Gridsearch - Démarrage Rapide

Guide ultra-simple pour lancer votre premier gridsearch avec **12 tests** (~1-2 heures).

## 🎯 Objectif

Tester **12 configurations** différentes pour voir l'influence de la **température** et du **repeat_penalty** sur vos générations.

## ⚡ Lancement Immédiat

```bash
# Avec le prompt par défaut
python gridsearch_local.py

# Ou avec votre prompt
python gridsearch_local.py "Un documentaire de 2 minutes sur les mines de charbon en 1920"
```

**C'est tout !** Le système va lancer 12 tests automatiquement.

## 📊 Les 12 Configurations Testées

| Test | Temperature | Repeat Penalty | Effet Attendu |
|------|-------------|----------------|---------------|
| 1 | 0.3 | 1.0 | Très cohérent, peu créatif, pas de pénalité |
| 2 | 0.3 | 1.05 | Très cohérent, peu créatif, légère pénalité |
| 3 | 0.3 | 1.1 | Très cohérent, peu créatif, pénalité forte |
| 4 | 0.5 | 1.0 | Équilibré, pas de pénalité |
| 5 | 0.5 | 1.05 | Équilibré, légère pénalité |
| 6 | 0.5 | 1.1 | Équilibré, pénalité forte |
| 7 | 0.7 | 1.0 | Créatif, cohérent, pas de pénalité |
| 8 | 0.7 | 1.05 | Créatif, cohérent, légère pénalité |
| 9 | 0.7 | 1.1 | Créatif, cohérent, pénalité forte |
| 10 | 0.9 | 1.0 | Très créatif, peut diverger, pas de pénalité |
| 11 | 0.9 | 1.05 | Très créatif, peut diverger, légère pénalité |
| 12 | 0.9 | 1.1 | Très créatif, peut diverger, pénalité forte |

**Paramètres fixes** : `max_tokens=3072`, `top_p=0.9`

## ⏱️ Durée

- **1-2 heures** pour 12 tests
- ~5-10 minutes par test
- Dépend de votre CPU et du modèle

## 📁 Résultats

```
output/gridsearch/run_20260128_170000/
├── comparison_report.txt           # ← LIRE EN PREMIER
├── comparison_report.json
├── test_001/                       # Temperature 0.3, Penalty 1.0
│   └── scenario.json               # ← Votre histoire générée
├── test_002/                       # Temperature 0.3, Penalty 1.05
│   └── scenario.json
├── test_007/                       # Temperature 0.7, Penalty 1.0
│   └── scenario.json               # ← Souvent la meilleure config
└── ...
```

## 📖 Lire les Résultats

### 1. Rapport Automatique

```bash
cat output/gridsearch/run_20260128_170000/comparison_report.txt
```

### 2. Analyses Détaillées

```bash
python analyze_gridsearch.py output/gridsearch/run_20260128_170000
```

### 3. Lire une Histoire Spécifique

```bash
# Voir l'histoire avec temperature=0.7, penalty=1.0 (test 7)
cat output/gridsearch/run_20260128_170000/test_007/scenario.json
```

## 🎯 Comparer les Histoires

### Méthode Visuelle (Recommandée)

```bash
# Ouvrir 3 histoires différentes
code output/gridsearch/run_XXX/test_001/scenario.json  # Temp 0.3
code output/gridsearch/run_XXX/test_007/scenario.json  # Temp 0.7
code output/gridsearch/run_XXX/test_010/scenario.json  # Temp 0.9
```

**Observez** :
- Longueur du texte
- Créativité vs répétitivité
- Cohérence narrative
- Richesse du vocabulaire

### Métriques Automatiques

Le rapport contient :
- **Nombre de mots** par configuration
- **Taux de succès** (certaines configs peuvent échouer)
- **Durée estimée** des scénarios

## 🔍 Ce Qu'il Faut Chercher

### Temperature Basse (0.3)
- ✅ Très cohérent
- ✅ Respecte bien les contraintes
- ❌ Peut être répétitif
- ❌ Moins créatif

### Temperature Moyenne (0.5-0.7)
- ✅ Bon équilibre
- ✅ Créatif mais cohérent
- ✅ Généralement le meilleur choix

### Temperature Haute (0.9)
- ✅ Très créatif
- ✅ Vocabulaire riche
- ❌ Peut diverger du sujet
- ❌ Moins prévisible

### Repeat Penalty
- **1.0** : Pas de pénalité, peut répéter
- **1.05** : Léger (recommandé)
- **1.1** : Fort, évite répétitions mais peut limiter cohérence

## 💡 Après le Gridsearch

### 1. Identifier la Meilleure Config

Regardez dans `comparison_report.txt` la section "MEILLEURES CONFIGURATIONS"

### 2. Appliquer dans main_local.py

Modifiez `main_local.py` pour utiliser les meilleurs paramètres :

```python
# Dans main_local.py, ligne ~70-80
ollama_client.client.default_temperature = 0.7        # Votre meilleure
ollama_client.client.default_repeat_penalty = 1.05   # Votre meilleure
```

### 3. Tester d'Autres Modèles

Une fois la meilleure config trouvée avec Qwen3:8b, testez avec d'autres modèles :

```python
# Dans gridsearch_local.py, ligne ~20
BASE_OLLAMA_CONFIG = {
    'model': 'llama3:latest',  # Changer ici
    'base_url': 'http://localhost:11434',
    'timeout': 600
}
```

Puis relancez :

```bash
# Télécharger le nouveau modèle
ollama pull llama3:latest

# Relancer avec la même config
python gridsearch_local.py "Votre même prompt"
```

## 🎛️ Modes Disponibles

### Mode STANDARD (par défaut) - 12 tests

```bash
python gridsearch_local.py
```

**Recommandé** pour l'exploration initiale.

### Mode RAPIDE - 2 tests

```bash
python gridsearch_local.py --quick
```

**Pour debug** uniquement (2 tests = pas assez pour conclure).

### Mode COMPLET - 32 tests

```bash
python gridsearch_local.py --full
```

**Pour validation finale** une fois que vous avez identifié les paramètres prometteurs.

## 🔧 Personnaliser

Pour tester d'autres valeurs, éditez `gridsearch_local.py` :

```python
# Ligne ~20
PARAM_GRID = {
    'temperature': [0.3, 0.5, 0.7, 0.9],      # Ajouter 0.4, 0.6, 0.8
    'max_tokens': [3072],                      # Tester 2048, 4096
    'top_p': [0.9],                            # Tester 0.85, 0.95
    'repeat_penalty': [1.0, 1.05, 1.1],       # Ajouter 1.15
}
```

Attention : plus de valeurs = plus de tests = plus long !

## 📊 Export pour Analyse Externe

```bash
# Générer CSV
python analyze_gridsearch.py output/gridsearch/run_XXX

# Ouvrir dans Excel
start output/gridsearch/run_XXX/results.csv  # Windows
open output/gridsearch/run_XXX/results.csv   # Mac
```

## 🐛 Problèmes Courants

### "Trop long, je veux arrêter"

`Ctrl+C` arrête proprement et sauvegarde les tests déjà faits.

### "Un test a échoué"

Normal ! Certaines configs extrêmes peuvent échouer. Le rapport indique lesquelles ont réussi.

### "Je veux tester moins de valeurs"

Éditez `PARAM_GRID` dans `gridsearch_local.py` :

```python
PARAM_GRID = {
    'temperature': [0.5, 0.7],       # Seulement 2 valeurs
    'repeat_penalty': [1.0, 1.05],   # Seulement 2 valeurs
    # = 2 × 2 = 4 tests
}
```

## 🎓 Workflow Complet

```bash
# 1. Premier gridsearch avec Qwen3:8b
python gridsearch_local.py "Documentaire 2min mines 1920"

# 2. Attendre 1-2h ☕

# 3. Analyser
python analyze_gridsearch.py output/gridsearch/run_20260128_170000

# 4. Lire les histoires
cat output/gridsearch/run_XXX/test_007/scenario.json  # Exemple

# 5. Identifier meilleure config (ex: temp=0.7, penalty=1.05)

# 6. Tester avec Llama3
#    - Modifier BASE_OLLAMA_CONFIG['model'] = 'llama3:latest'
#    - Fixer PARAM_GRID avec seulement les bonnes valeurs
python gridsearch_local.py "Même prompt"

# 7. Comparer Qwen3 vs Llama3

# 8. Choisir le meilleur modèle + config

# 9. Utiliser en production dans main_local.py
```

## 📞 Aide Rapide

```bash
# Lancer gridsearch standard (12 tests)
python gridsearch_local.py

# Voir les runs disponibles
ls output/gridsearch/

# Analyser le dernier run
python analyze_gridsearch.py output/gridsearch/$(ls -t output/gridsearch/ | head -1)

# Lire une histoire
cat output/gridsearch/run_XXX/test_007/scenario.json
```

---

**🚀 C'est parti ! Lancez votre premier gridsearch :**

```bash
python gridsearch_local.py
```

**Durée : 1-2 heures | Tests : 12 | Résultats : output/gridsearch/**
