# 🎛️ Gridsearch Configuration JSON - Guide

Test systématique de l'influence des **paramètres de configuration** sur les générations.

## 🎯 Objectif

Tester l'impact des paramètres narratifs :
- **Forme** : documentaire, interview, témoignage, reportage...
- **Ton** : neutre, émotionnel, dramatique...
- **Axe narratif** : chronologique, thématique, mixte...
- **Durée** : différentes longueurs de scénarios

## 🆚 Différence avec gridsearch_local.py

| Aspect | gridsearch_local.py | gridsearch_config.py |
|--------|---------------------|----------------------|
| **Teste** | Paramètres LLM | Paramètres narratifs |
| **Variables** | temperature, tokens, top_p | forme, ton, axe_narratif |
| **Usage** | Trouver meilleurs params LLM | Comparer styles narratifs |
| **Ordre** | **1er** (trouver params optimaux) | **2ème** (tester styles) |

## 📊 Workflow Recommandé

### Étape 1 : Optimiser les Paramètres LLM

```bash
# D'abord, trouver les meilleurs paramètres LLM
python gridsearch_local.py
```

**Résultat** : Par exemple `temp=0.7, penalty=1.05`

### Étape 2 : Tester les Configurations Narratives

```bash
# Ensuite, tester différentes formes/tons avec params LLM optimaux
python gridsearch_config.py
```

**Résultat** : Comparer documentaire vs témoignage, neutre vs émotionnel, etc.

## 🚀 Utilisation

### Mode STANDARD (9 tests) - Recommandé

```bash
python gridsearch_config.py
# ou avec prompt personnalisé
python gridsearch_config.py "Documentaire sur les mines de 1920"
```

**Configuration testée** :
- 3 formes : documentaire, reportage, témoignage
- 3 tons : neutre, émotionnel, dramatique
- 1 axe : mixte (fixe)
- 1 durée : 180s (fixe)

**Total : 3 × 3 = 9 tests**
**Durée : ~1-2 heures**

### Mode RAPIDE (2 tests) - Debug

```bash
python gridsearch_config.py --quick
```

**Total : 2 tests**
**Durée : ~15-30 minutes**

### Mode COMPLET (36 tests) - Exhaustif

```bash
python gridsearch_config.py --full
```

**Configuration testée** :
- 4 formes : documentaire, interview, reportage, témoignage
- 3 tons : neutre, émotionnel, dramatique
- 3 axes : chronologique, mixte, thématique
- 1 durée : 180s

**Total : 4 × 3 × 3 = 36 tests**
**Durée : ~4-6 heures**

## 📁 Résultats

```
output/gridsearch_config/run_20260128_180000/
├── gridsearch_config.json          # Configuration du run
├── comparison_report.json          # Rapport JSON
├── comparison_report.txt           # Rapport lisible
├── test_001/                       # Documentaire + Neutre
│   ├── metadata.json
│   ├── scenario.json               # 🎬 HISTOIRE GÉNÉRÉE
│   └── ...
├── test_002/                       # Documentaire + Émotionnel
│   ├── scenario.json
│   └── ...
├── test_005/                       # Reportage + Émotionnel
│   └── ...
└── ...
```

## 🔍 Les 9 Configurations (Mode Standard)

| Test | Forme | Ton | Résultat Attendu |
|------|-------|-----|------------------|
| 1 | Documentaire | Neutre | Factuel, objectif, informatif |
| 2 | Documentaire | Émotionnel | Factuel mais avec empathie |
| 3 | Documentaire | Dramatique | Factuel avec tension narrative |
| 4 | Reportage | Neutre | Journalistique, direct |
| 5 | Reportage | Émotionnel | Journalistique avec humain |
| 6 | Reportage | Dramatique | Immersif, intense |
| 7 | Témoignage | Neutre | Personnel mais sobre |
| 8 | Témoignage | Émotionnel | Personnel, intime, vécu |
| 9 | Témoignage | Dramatique | Personnel, intense, vivant |

## 📖 Analyser les Résultats

### 1. Rapport Automatique

```bash
cat output/gridsearch_config/run_XXX/comparison_report.txt
```

### 2. Comparer les Histoires

```bash
# Documentaire neutre vs émotionnel vs dramatique
code output/gridsearch_config/run_XXX/test_001/scenario.json  # Doc + Neutre
code output/gridsearch_config/run_XXX/test_002/scenario.json  # Doc + Émotionnel
code output/gridsearch_config/run_XXX/test_003/scenario.json  # Doc + Dramatique
```

### 3. Analyse Python

```bash
python analyze_gridsearch.py output/gridsearch_config/run_XXX
```

(Le même analyseur fonctionne pour les deux types de gridsearch)

## 🎭 Description des Paramètres

### Forme

#### Documentaire
- Style informatif et factuel
- Structure équilibrée
- Objectivité

#### Interview
- Format question/réponse
- Paroles directes
- Témoignages multiples

#### Reportage
- Style journalistique
- Immersion terrain
- Observations directes

#### Témoignage
- Première personne
- Personnel et intime
- Vécu subjectif

### Ton

#### Neutre Informatif
- Objectif et factuel
- Pas d'émotion excessive
- Pédagogique

#### Émotionnel Personnel
- Empathie et ressenti
- Connexion humaine
- Vécu personnel

#### Dramatique Immersif
- Tension narrative
- Suspense et intensité
- Immersion totale

### Axe Narratif

#### Chronologique
- Suit l'ordre temporel
- Cause → effet
- Progression linéaire

#### Thématique
- Organisé par thèmes
- Plusieurs angles
- Non-linéaire

#### Mixte
- Combine chrono + thématique
- Flexible et équilibré
- Adaptatif

## 💡 Personnaliser les Tests

Éditez `gridsearch_config.py` :

```python
# Ligne ~40
CONFIG_GRID = {
    'forme': ['documentaire', 'conte'],  # Ajouter 'conte'
    'ton': ['neutre_informatif', 'poetique_contemplatif'],  # Changer ton
    'axe_narratif': ['chronologique', 'thematique'],  # Tester 2 axes
    'duree': [120, 240],  # Tester 2 durées (2min et 4min)
}
# = 2 × 2 × 2 × 2 = 16 tests
```

### Toutes les Formes Disponibles

```python
'forme': [
    'documentaire',
    'interview',
    'conte',
    'témoignage',
    'reportage',
    'fiction_historique',
    'podcast_narratif'
]
```

### Tous les Tons Disponibles

```python
'ton': [
    'neutre_informatif',
    'emotionnel_personnel',
    'dramatique_immersif',
    'pedagogique_accessible',
    'poetique_contemplatif',
    'journalistique_factuel',
    'intimiste_confidentiel'
]
```

## 🎯 Cas d'Usage

### Comparer Documentaire vs Témoignage

```python
CONFIG_GRID = {
    'forme': ['documentaire', 'témoignage'],
    'ton': ['neutre_informatif'],
    'axe_narratif': ['mixte'],
    'duree': [180],
}
# = 2 tests
```

### Comparer Tous les Tons

```python
CONFIG_GRID = {
    'forme': ['documentaire'],  # Fixe
    'ton': [
        'neutre_informatif',
        'emotionnel_personnel',
        'dramatique_immersif',
        'pedagogique_accessible',
        'poetique_contemplatif'
    ],
    'axe_narratif': ['mixte'],
    'duree': [180],
}
# = 5 tests
```

### Tester Différentes Durées

```python
CONFIG_GRID = {
    'forme': ['documentaire'],
    'ton': ['neutre_informatif'],
    'axe_narratif': ['mixte'],
    'duree': [60, 120, 180, 300, 420],  # 1min à 7min
}
# = 5 tests
```

## 📊 Workflow Complet : LLM + Config

### 1. Optimiser LLM (gridsearch_local.py)

```bash
# Trouver temp, top_p, repeat_penalty optimaux
python gridsearch_local.py
```

**Résultat** : `temp=0.7, penalty=1.05`

### 2. Appliquer dans gridsearch_config.py

Modifier `FIXED_LLM_PARAMS` ligne ~35 :

```python
FIXED_LLM_PARAMS = {
    'temperature': 0.7,        # Votre meilleur
    'max_tokens': 3072,
    'top_p': 0.9,
    'repeat_penalty': 1.05,   # Votre meilleur
}
```

### 3. Tester Configurations (gridsearch_config.py)

```bash
# Tester formes/tons avec params LLM optimaux
python gridsearch_config.py
```

### 4. Comparer Résultats

```bash
# Analyser
python analyze_gridsearch.py output/gridsearch_config/run_XXX

# Lire les histoires
cat output/gridsearch_config/run_XXX/test_001/scenario.json
```

### 5. Choisir Config Finale

Par exemple :
- **Meilleur** : Reportage + Émotionnel
- **LLM** : temp=0.7, penalty=1.05
- **Durée** : 180s

### 6. Utiliser en Production

Modifier `main_local.py` pour utiliser cette config par défaut.

## 🔄 Comparer Modèles avec Configs

Une fois config optimale trouvée, tester avec autres modèles :

```bash
# 1. Config optimale trouvée avec Qwen3:8b
python gridsearch_config.py  # Résultats: Reportage + Émotionnel

# 2. Tester avec Llama3
# Modifier BASE_OLLAMA_CONFIG['model'] = 'llama3:latest'
ollama pull llama3:latest
python gridsearch_config.py  # Même grille

# 3. Comparer les histoires
cat output/gridsearch_config/run_XXX_qwen/test_005/scenario.json
cat output/gridsearch_config/run_XXX_llama/test_005/scenario.json
```

## 📈 Métriques Collectées

Pour chaque configuration :
- ✅ **Succès/Échec**
- 📝 **Nombre de mots**
- 🎬 **Nombre de parties** narratives
- ⏱️ **Durée estimée** du scénario
- 🎭 **Style narratif** généré

## 🐛 Dépannage

### "Tous les tests donnent le même résultat"

Les différences peuvent être subtiles. Regardez :
- Le **vocabulaire** utilisé
- La **structure** des phrases
- Le **point de vue** narratif (3ème vs 1ère personne)

### "Je ne vois pas la différence entre les tons"

Normal avec certains modèles. Les tons subtils (poétique, intimiste) sont parfois difficiles à distinguer. Focalisez sur :
- Neutre vs Émotionnel vs Dramatique (+ marqués)

### "Une config échoue systématiquement"

Certaines combinaisons peuvent être incompatibles. Par exemple :
- Interview + Chronologique strict peut être difficile

## 📚 Ordre Recommandé

1. **gridsearch_local.py** → Trouver meilleurs paramètres LLM
2. **gridsearch_config.py** → Trouver meilleure forme/ton
3. **Comparer modèles** → Tester avec Llama3, Mistral, etc.
4. **Production** → Utiliser config finale dans main_local.py

---

**🎬 Lancez votre gridsearch de configuration :**

```bash
python gridsearch_config.py
```

**9 tests | ~1-2h | Comparez styles narratifs avec LLM optimisé !**
