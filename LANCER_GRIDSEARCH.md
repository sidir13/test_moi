# 🚀 Comment Lancer les Gridsearch

Guide simple pour lancer et comprendre les deux types de gridsearch.

## 🎯 Deux Types de Gridsearch

### 1. Gridsearch LLM (`gridsearch_local.py`)

**Teste** : Paramètres techniques du modèle
- Temperature (créativité)
- Repeat penalty (éviter répétitions)
- Max tokens (longueur)
- Top P (diversité)

**Objectif** : Trouver les **meilleurs paramètres LLM** pour votre modèle

### 2. Gridsearch Config (`gridsearch_config.py`)

**Teste** : Paramètres narratifs de configuration
- Forme (documentaire, témoignage, reportage...)
- Ton (neutre, émotionnel, dramatique...)
- Axe narratif (chronologique, thématique, mixte)
- Durée

**Objectif** : Trouver le **meilleur style narratif** pour votre usage

## 📊 Ordre Recommandé

### Étape 1 : Optimiser LLM (EN PREMIER) ⭐

```bash
python gridsearch_local.py
```

**Pourquoi en premier ?**
- Les paramètres LLM affectent TOUT
- Il faut les optimiser AVANT de tester les styles narratifs

**Résultat attendu :**
```
Meilleure config : temp=0.7, penalty=1.05
```

**Durée : 1-2 heures (12 tests)**

---

### Étape 2 : Optimiser Configuration (EN SECOND)

```bash
python gridsearch_config.py
```

**Pourquoi en second ?**
- Utilise les paramètres LLM optimaux trouvés à l'étape 1
- Compare les styles narratifs avec le meilleur LLM

**Résultat attendu :**
```
Meilleur style : Reportage + Ton émotionnel
```

**Durée : 1-2 heures (9 tests)**

---

## 🔧 Lancement Détaillé

### Gridsearch LLM

#### Mode Standard (Recommandé)

```bash
python gridsearch_local.py
```

**Teste 12 configurations** :
- 4 températures × 3 repeat_penalty
- Params fixes : max_tokens=3072, top_p=0.9

#### Avec Prompt Personnalisé

```bash
python gridsearch_local.py "Un documentaire de 2 minutes sur les mines de charbon en 1920"
```

#### Mode Rapide (Debug)

```bash
python gridsearch_local.py --quick
```

**2 tests seulement** (~15-30 min)

#### Mode Complet (Validation)

```bash
python gridsearch_local.py --full
```

**32 tests** (~4-8h) - Pour validation finale uniquement

---

### Gridsearch Configuration

#### Mode Standard (Recommandé)

```bash
python gridsearch_config.py
```

**Teste 9 configurations** :
- 3 formes × 3 tons
- Params fixes : axe=mixte, durée=180s

#### Avec Prompt Personnalisé

```bash
python gridsearch_config.py "Un documentaire de 2 minutes sur les mines de charbon en 1920"
```

**Important** : Utilisez le **même prompt** que pour gridsearch LLM pour comparer

#### Mode Rapide (Debug)

```bash
python gridsearch_config.py --quick
```

**2 tests seulement** (~15-30 min)

#### Mode Complet (Validation)

```bash
python gridsearch_config.py --full
```

**36 tests** (~4-6h) - Pour validation finale

---

## 📁 Résultats

### Gridsearch LLM

```
output/gridsearch/run_20260128_170000/
├── comparison_report.txt           # Lire en premier
├── test_001/                       # temp=0.3, penalty=1.0
│   └── scenario.json
├── test_007/                       # temp=0.7, penalty=1.0
│   └── scenario.json
└── ...
```

### Gridsearch Config

```
output/gridsearch_config/run_20260128_190000/
├── comparison_report.txt           # Lire en premier
├── test_001/                       # Documentaire + Neutre
│   └── scenario.json
├── test_005/                       # Reportage + Émotionnel
│   └── scenario.json
└── ...
```

---

## 📖 Analyser les Résultats

### Pour les Deux Types

```bash
# Gridsearch LLM
python analyze_gridsearch.py output/gridsearch/run_20260128_170000

# Gridsearch Config
python analyze_gridsearch.py output/gridsearch_config/run_20260128_190000
```

### Lire le Rapport

```bash
# Gridsearch LLM
cat output/gridsearch/run_20260128_170000/comparison_report.txt

# Gridsearch Config
cat output/gridsearch_config/run_20260128_190000/comparison_report.txt
```

### Lire une Histoire Spécifique

```bash
# Exemple : temp=0.7, penalty=1.0
cat output/gridsearch/run_XXX/test_007/scenario.json

# Exemple : Reportage + Émotionnel
cat output/gridsearch_config/run_XXX/test_005/scenario.json
```

---

## 🎯 Workflow Complet Pas à Pas

### Jour 1 : Optimiser LLM

```bash
# 1. Lancer gridsearch LLM
python gridsearch_local.py "Documentaire 2min mines 1920"

# 2. Attendre 1-2h ☕

# 3. Analyser résultats
python analyze_gridsearch.py output/gridsearch/run_20260128_170000

# 4. Lire le rapport
cat output/gridsearch/run_20260128_170000/comparison_report.txt

# 5. Identifier meilleure config
# Exemple : temp=0.7, penalty=1.05
```

### Jour 2 : Tester Configurations

```bash
# 1. Modifier gridsearch_config.py ligne 35
# FIXED_LLM_PARAMS = {
#     'temperature': 0.7,        # ← Votre meilleur
#     'repeat_penalty': 1.05,    # ← Votre meilleur
# }

# 2. Lancer gridsearch config avec MÊME prompt
python gridsearch_config.py "Documentaire 2min mines 1920"

# 3. Attendre 1-2h ☕

# 4. Analyser résultats
python analyze_gridsearch.py output/gridsearch_config/run_20260128_190000

# 5. Comparer les histoires
cat output/gridsearch_config/run_XXX/test_001/scenario.json  # Doc + Neutre
cat output/gridsearch_config/run_XXX/test_005/scenario.json  # Rep + Émo

# 6. Choisir le meilleur style
# Exemple : Reportage + Émotionnel
```

### Jour 3 : Tester Autre Modèle

```bash
# 1. Télécharger Llama3
ollama pull llama3:latest

# 2. Modifier gridsearch_local.py ligne 20
# BASE_OLLAMA_CONFIG['model'] = 'llama3:latest'

# 3. Relancer gridsearch LLM
python gridsearch_local.py "Documentaire 2min mines 1920"

# 4. Comparer Qwen3 vs Llama3
cat output/gridsearch/run_XXX_qwen/test_007/scenario.json
cat output/gridsearch/run_XXX_llama/test_007/scenario.json
```

---

## 🎨 Personnaliser les Tests

### Changer Paramètres LLM Testés

Éditer `gridsearch_local.py` ligne ~20 :

```python
PARAM_GRID = {
    'temperature': [0.5, 0.6, 0.7, 0.8],  # Affiner autour de 0.7
    'repeat_penalty': [1.0, 1.05],        # Seulement 2 valeurs
    'max_tokens': [3072],                 # Fixe
    'top_p': [0.9],                       # Fixe
}
# = 4 × 2 = 8 tests
```

### Changer Configurations Testées

Éditer `gridsearch_config.py` ligne ~40 :

```python
CONFIG_GRID = {
    'forme': ['documentaire', 'conte'],           # Tester conte
    'ton': ['neutre_informatif', 'poetique_contemplatif'],  # Tester poétique
    'axe_narratif': ['mixte'],
    'duree': [120, 240],                          # Tester 2 durées
}
# = 2 × 2 × 1 × 2 = 8 tests
```

---

## ⏱️ Temps Estimés

| Gridsearch | Mode | Tests | Durée |
|-----------|------|-------|-------|
| LLM | Rapide | 2 | 15-30 min |
| LLM | **Standard** | 12 | **1-2h** ⭐ |
| LLM | Complet | 32 | 4-8h |
| Config | Rapide | 2 | 15-30 min |
| Config | **Standard** | 9 | **1-2h** ⭐ |
| Config | Complet | 36 | 4-6h |

**Total workflow complet** : 2-4 heures (LLM + Config en mode standard)

---

## 💡 Astuces

### Utiliser un Prompt Court

```bash
# Plus rapide pour tests
python gridsearch_local.py "Une scène d'usine, 1 minute"
```

### Interrompre et Reprendre

`Ctrl+C` sauvegarde les tests déjà faits. Pas besoin de tout refaire.

### Comparer Visuellement

```bash
# Ouvrir plusieurs histoires côte à côte
code output/gridsearch/run_XXX/test_001/scenario.json
code output/gridsearch/run_XXX/test_007/scenario.json
code output/gridsearch/run_XXX/test_012/scenario.json
```

### Export pour Excel

```bash
python analyze_gridsearch.py output/gridsearch/run_XXX
# Génère results.csv
start output/gridsearch/run_XXX/results.csv
```

---

## 🐛 Problèmes Courants

### "Je ne vois pas de différence entre les tests"

- Les différences peuvent être subtiles
- Focalisez sur extrêmes : temp=0.3 vs temp=0.9
- Lisez plusieurs paragraphes, pas juste le début

### "Tous les tests échouent"

```bash
# Vérifier Ollama
python check_ollama.py

# Augmenter timeout dans les scripts si besoin
```

### "C'est trop long"

- Utilisez `--quick` pour commencer
- Testez avec prompt plus court
- Réduisez nombre de valeurs dans PARAM_GRID

---

## 📚 Documentation Complète

- **`GRIDSEARCH_QUICKSTART.md`** : Guide rapide gridsearch LLM
- **`GRIDSEARCH_GUIDE.md`** : Guide complet gridsearch LLM
- **`GRIDSEARCH_CONFIG_GUIDE.md`** : Guide complet gridsearch Config
- **`EXEMPLES_PROMPTS.md`** : 50+ exemples de prompts

---

## 🚀 Commandes Rapides

```bash
# Workflow complet en 2 commandes
python gridsearch_local.py          # 1-2h
python gridsearch_config.py         # 1-2h

# Analyser les deux
python analyze_gridsearch.py output/gridsearch/run_XXX
python analyze_gridsearch.py output/gridsearch_config/run_XXX
```

**Total : 2-4 heures pour tout optimiser !** 🎯
