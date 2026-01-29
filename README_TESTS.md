# 🧪 Guide des Tests Locaux

Résumé des outils disponibles pour tester le système avec Ollama.

## 📋 Outils Disponibles

### 1️⃣ `main_local.py` - Test Simple

**Usage** : Test unique avec un prompt

```bash
# Mode interactif
python main_local.py

# Mode direct
python main_local.py "Votre prompt ici"
```

**Résultats** : `output/local_tests/`

**Durée** : ~5-15 minutes par test

---

### 2️⃣ `gridsearch_local.py` - Test Paramètres LLM

**Usage** : Test multiple avec différents paramètres LLM (temperature, top_p, etc.)

```bash
# Mode standard (12 tests) - RECOMMANDÉ
python gridsearch_local.py

# Mode rapide (2 tests) - Debug
python gridsearch_local.py --quick

# Mode complet (32 tests) - Validation
python gridsearch_local.py --full
```

**Teste** : temperature, repeat_penalty, max_tokens, top_p

**Résultats** : `output/gridsearch/run_YYYYMMDD_HHMMSS/`

**Durée** :
- Mode rapide : ~15-30 minutes (2 tests)
- Mode standard : ~1-2 heures (12 tests) ⭐
- Mode complet : ~4-8 heures (32 tests)

---

### 3️⃣ `gridsearch_config.py` - Test Paramètres Configuration

**Usage** : Test multiple avec différentes configurations narratives (forme, ton, etc.)

```bash
# Mode standard (9 tests) - RECOMMANDÉ
python gridsearch_config.py

# Mode rapide (2 tests) - Debug
python gridsearch_config.py --quick

# Mode complet (36 tests) - Validation
python gridsearch_config.py --full
```

**Teste** : forme (documentaire/témoignage), ton (neutre/émotionnel), axe narratif

**Résultats** : `output/gridsearch_config/run_YYYYMMDD_HHMMSS/`

**Durée** :
- Mode rapide : ~15-30 minutes (2 tests)
- Mode standard : ~1-2 heures (9 tests) ⭐
- Mode complet : ~4-6 heures (36 tests)

---

### 4️⃣ `analyze_gridsearch.py` - Analyse Résultats

**Usage** : Analyse les résultats d'un gridsearch

```bash
python analyze_gridsearch.py output/gridsearch/run_YYYYMMDD_HHMMSS
```

**Génère** :
- Résumé statistiques
- Impact par paramètre
- Meilleures configurations
- Export CSV

---

### 4️⃣ `check_ollama.py` - Vérification Ollama

**Usage** : Vérifie qu'Ollama fonctionne

```bash
python check_ollama.py
```

**Vérifie** :
- Connexion Ollama
- Modèles disponibles
- Test de génération simple

---

### 5️⃣ `check_imports.py` - Vérification Imports

**Usage** : Vérifie les imports manquants

```bash
python check_imports.py
```

**Utile** : Après modifications du code

---

## 🎯 Workflows Recommandés

### Découverte (Première Fois)

```bash
# 1. Vérifier setup
python check_ollama.py

# 2. Test simple
python main_local.py

# 3. Consulter résultats
cat output/local_tests/scenario_*.json
```

### Optimisation (Trouver Meilleurs Paramètres)

```bash
# 1. Gridsearch standard (12 tests)
python gridsearch_local.py "Prompt court"

# 2. Analyser résultats
python analyze_gridsearch.py output/gridsearch/run_XXX

# 3. Lire les meilleures histoires
cat output/gridsearch/run_XXX/test_007/scenario.json

# 4. Identifier config optimale (ex: temp=0.7, penalty=1.05)

# 5. Tester avec autre modèle (ex: llama3)
# Modifier BASE_OLLAMA_CONFIG dans gridsearch_local.py
ollama pull llama3:latest
python gridsearch_local.py "Même prompt"

# 6. Comparer modèles et choisir le meilleur
```

### Production (Génération Régulière)

```bash
# Utiliser paramètres optimaux trouvés
# Modifier OLLAMA_CONFIG dans main_local.py

python main_local.py "Votre prompt de production"
```

---

## 📊 Paramètres Testés (Gridsearch)

| Paramètre | Valeurs Testées | Impact |
|-----------|-----------------|--------|
| **temperature** | 0.3, 0.5, 0.7, 0.9 | Créativité vs Cohérence |
| **max_tokens** | 2048, 4096 | Longueur réponses |
| **top_p** | 0.9, 0.95 | Diversité vocabulaire |
| **repeat_penalty** | 1.0, 1.1 | Éviter répétitions |

---

## 📁 Structure des Outputs

```
output/
├── local_tests/              # Tests simples (main_local.py)
│   ├── config_TIMESTAMP.json
│   ├── structure_TIMESTAMP.json
│   ├── scenario_TIMESTAMP.json
│   └── timeline_TIMESTAMP.json
│
└── gridsearch/              # Gridsearch (gridsearch_local.py)
    └── run_YYYYMMDD_HHMMSS/
        ├── gridsearch_config.json
        ├── comparison_report.json
        ├── comparison_report.txt
        ├── results.csv
        └── test_XXX/
            ├── metadata.json
            ├── config.json
            ├── structure.json
            ├── scenario.json
            └── timeline.json
```

---

## ⚙️ Configuration

### Changer le Modèle Ollama

**Dans `main_local.py`** et **`gridsearch_local.py`** :

```python
BASE_OLLAMA_CONFIG = {
    'model': 'qwen3:8b',  # Modifier ici
    'base_url': 'http://localhost:11434',
    'timeout': 600
}
```

### Modifier la Grille de Paramètres

**Dans `gridsearch_local.py`** :

```python
PARAM_GRID = {
    'temperature': [0.3, 0.5, 0.7, 0.9],  # Ajouter/retirer valeurs
    'max_tokens': [2048, 4096, 8192],     # Ex: ajouter 8192
    'top_p': [0.85, 0.9, 0.95],           # Ex: ajouter 0.85
    'repeat_penalty': [1.0, 1.05, 1.1],   # Ex: ajouter 1.05
}
```

### Modifier le Timeout

**Dans `main_local.py`** :

```python
OLLAMA_CONFIG = {
    'timeout': 900  # 15 minutes au lieu de 10
}
```

---

## 🚀 Démarrage Rapide

### Premier Test

```bash
# 1. Setup (une seule fois)
.\setup_project.ps1  # Windows
./setup_project.sh   # Linux/Mac

# 2. Vérifier Ollama
python check_ollama.py

# 3. Premier test
python main_local.py
```

### Gridsearch Rapide

```bash
python gridsearch_local.py --quick
```

### Analyser Résultats

```bash
# Trouver le dernier run
ls output/gridsearch/

# Analyser
python analyze_gridsearch.py output/gridsearch/run_20260128_160000
```

---

## 💡 Astuces

### Prompt Court pour Tests

```bash
python main_local.py "Une scène d'usine, 1 minute"
# Plus rapide qu'un documentaire de 5 minutes
```

### Comparer Visuellement

```bash
# Ouvrir 2 scénarios côte à côte
code output/gridsearch/run_XXX/test_001/scenario.json
code output/gridsearch/run_XXX/test_015/scenario.json
```

### Export pour Excel

```bash
python analyze_gridsearch.py output/gridsearch/run_XXX
# Génère results.csv
# Ouvrir dans Excel pour graphiques
```

### Interrompre Proprement

`Ctrl+C` sauvegarde les tests déjà terminés

---

## 📚 Documentation Détaillée

- **`GRIDSEARCH_GUIDE.md`** : Guide complet du gridsearch
- **`EXEMPLES_PROMPTS.md`** : 50+ exemples de prompts
- **`SETUP_UV.md`** : Installation avec UV
- **`main_local.py`** : Code source commenté

---

## 🐛 Problèmes Courants

### "Cannot connect to Ollama"

```bash
# Lancer Ollama
ollama serve
```

### "Model not found"

```bash
# Télécharger le modèle
ollama pull qwen3:8b
```

### "Tests trop lents"

- Utilisez `--quick`
- Prompt plus court
- Réduire `max_tokens` dans la grille

### "Manque de mémoire"

- Fermer autres applications
- Redémarrer Ollama
- Réduire `max_tokens`

---

## 📞 Aide Rapide

```bash
# Vérifier tout
python check_ollama.py
python check_imports.py

# Test simple
python main_local.py "test simple"

# Gridsearch rapide
python gridsearch_local.py --quick

# Analyser dernier run
python analyze_gridsearch.py output/gridsearch/$(ls -t output/gridsearch/ | head -1)
```

---

**🎯 Prêt pour vos tests !**
