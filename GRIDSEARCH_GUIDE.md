# 🔬 Guide du Gridsearch LLM

Système de test automatisé pour évaluer l'influence des paramètres LLM sur la qualité des générations.

## 🎯 Objectif

Tester différentes combinaisons de paramètres (température, max_tokens, top_p, etc.) et comparer les résultats pour trouver la configuration optimale.

## 📊 Paramètres Testés

### Temperature (0.1 - 1.0)
- **0.1-0.3** : Très déterministe, cohérent, peu créatif
- **0.4-0.6** : Équilibré
- **0.7-0.9** : Plus créatif, varié, moins prévisible
- **1.0+** : Très créatif, risque d'incohérences

### Max Tokens (1024 - 8192)
- **1024-2048** : Réponses courtes
- **2048-4096** : Standard, recommandé
- **4096-8192** : Réponses longues et détaillées

### Top P (0.8 - 1.0)
- **0.8-0.9** : Focus sur tokens probables
- **0.9-0.95** : Équilibré (recommandé)
- **0.95-1.0** : Plus de diversité

### Repeat Penalty (1.0 - 1.2)
- **1.0** : Pas de pénalité
- **1.05-1.1** : Léger (recommandé)
- **1.1-1.2** : Fort (évite répétitions)

## 🚀 Utilisation

### Mode STANDARD (Recommandé) - 12 tests

```bash
# Mode par défaut - 12 tests en ~1-2h
python gridsearch_local.py

# Avec prompt personnalisé
python gridsearch_local.py "Un documentaire de 2 minutes sur les mines en 1920"
```

**Configuration** : 4 températures × 3 repeat_penalty = **12 tests**
- Temperature: 0.3, 0.5, 0.7, 0.9
- Repeat Penalty: 1.0, 1.05, 1.1
- Max Tokens: 3072 (fixe)
- Top P: 0.9 (fixe)

Durée estimée : **1-2 heures**

### Mode RAPIDE (Debug) - 2 tests

```bash
# Test minimal pour debug
python gridsearch_local.py --quick
```

**Configuration** : 2 températures × 1 repeat_penalty = **2 tests**
- Temperature: 0.3, 0.7
- Autres paramètres fixes

Durée estimée : **15-30 minutes**

### Mode COMPLET (Validation Finale) - 32 tests

```bash
# Test exhaustif
python gridsearch_local.py --full
```

**Configuration** : 4 temp × 2 tokens × 2 top_p × 2 penalty = **32 tests**

Durée estimée : **4-8 heures**

## 📁 Structure des Résultats

```
output/gridsearch/
└── run_20260128_160000/
    ├── gridsearch_config.json          # Configuration du run
    ├── comparison_report.json          # Rapport détaillé JSON
    ├── comparison_report.txt           # Rapport lisible
    ├── results.csv                     # Export CSV (après analyse)
    ├── test_001/                       # Résultats test 1
    │   ├── metadata.json               # Paramètres + métriques
    │   ├── config.json                 # Output Agent 0
    │   ├── structure.json              # Output Agent 1
    │   ├── scenario.json               # Output Agent 2
    │   └── timeline.json               # Output Agent 3
    ├── test_002/                       # Résultats test 2
    │   └── ...
    └── ...
```

## 📈 Analyse des Résultats

### 1. Rapport Automatique

Le rapport est généré automatiquement :

```bash
cat output/gridsearch/run_YYYYMMDD_HHMMSS/comparison_report.txt
```

### 2. Analyse Détaillée

```bash
python analyze_gridsearch.py output/gridsearch/run_YYYYMMDD_HHMMSS
```

Affiche :
- ✅ Résumé global (succès/échecs)
- 📊 Impact de chaque paramètre
- 🏆 Meilleures configurations
- 🌡️ Focus sur la température
- 📄 Export CSV pour Excel/R/Python

### 3. Analyse Manuelle

Consultez les fichiers JSON individuels :

```bash
# Voir le scénario généré avec température = 0.3
cat output/gridsearch/run_YYYYMMDD_HHMMSS/test_001/scenario.json
```

## 🔍 Métriques Collectées

Pour chaque test :
- ✅ **Succès/Échec**
- 📝 **Nombre de mots** générés
- 🎬 **Nombre de parties** narratives
- ⏱️ **Durée estimée** du scénario
- 🕐 **Temps d'exécution** par agent

## 📊 Exemples de Questions à Répondre

### Quelle température génère le plus de contenu ?

```bash
python analyze_gridsearch.py output/gridsearch/run_XXX
# Regarder section "FOCUS: IMPACT DE LA TEMPÉRATURE"
```

### Quelle config est la plus créative ?

Comparer les scénarios manuellement :
- Température haute (0.9) = plus créatif
- Température basse (0.3) = plus cohérent

### Quelle config est la plus rapide ?

Regarder `metadata.json` de chaque test pour les durées d'exécution.

### Configuration optimale pour mon usage ?

Dépend de vos besoins :
- **Cohérence** : temp=0.3, penalty=1.1
- **Créativité** : temp=0.8, penalty=1.0
- **Équilibre** : temp=0.5, penalty=1.05

## 🎛️ Personnaliser les Paramètres

Éditez `gridsearch_local.py` :

```python
# Grille complète
PARAM_GRID = {
    'temperature': [0.3, 0.5, 0.7, 0.9],       # Modifier ici
    'max_tokens': [2048, 4096],                # Ajouter/retirer valeurs
    'top_p': [0.9, 0.95],
    'repeat_penalty': [1.0, 1.1],
}

# Grille rapide
PARAM_GRID_QUICK = {
    'temperature': [0.3, 0.7],                 # 2 valeurs minimum
    'max_tokens': [2048],
    'top_p': [0.9],
    'repeat_penalty': [1.0],
}
```

Nombre de tests = produit cartésien des valeurs.

Exemple : 4 temp × 3 tokens × 2 top_p = **24 tests**

## ⚡ Conseils

### Pour Démarrer

1. **Commencez en mode rapide** :
   ```bash
   python gridsearch_local.py --quick
   ```

2. **Analysez les résultats** :
   ```bash
   python analyze_gridsearch.py output/gridsearch/run_XXX
   ```

3. **Lisez quelques scénarios** pour comprendre l'impact

4. **Affinez** votre grille selon vos observations

### Pour Optimiser

- **Testez d'abord la température** seule (paramètre le plus influent)
- **Fixez les autres** à leurs valeurs par défaut
- **Puis testez les autres** paramètres un par un

### Pour Accélérer

- Utilisez un **prompt court** (1-2 minutes)
- **Limitez les valeurs** dans la grille
- Testez sur **moins d'agents** (ex: seulement Agent 0 et 1)

## 🛠️ Modification Avancée

### Tester Seulement Certains Agents

Éditez `gridsearch_local.py`, fonction `run_single_test()` :

```python
# Commenter les agents non nécessaires
# Agent 2
# scenario = agent_2.write_complete_scenario(structure, config)

# Agent 3
# timeline = agent_3.create_audio_timeline(scenario, None, config)
```

### Ajouter d'Autres Métriques

Dans `run_single_test()` :

```python
# Ajouter vos métriques personnalisées
results['metrics']['custom_metric'] = votre_calcul
```

### Paralléliser les Tests

Pour l'instant séquentiel. Pour paralléliser :
- Utiliser `multiprocessing`
- Attention : charge CPU/Ollama

## 📝 Exemple de Workflow Complet

```bash
# 1. Test rapide initial
python gridsearch_local.py --quick "Documentaire 3min grève 1905"

# 2. Analyser
python analyze_gridsearch.py output/gridsearch/run_20260128_160000

# 3. Identifier meilleure température (ex: 0.7)

# 4. Modifier grille pour focus sur 0.7
# Éditer PARAM_GRID dans gridsearch_local.py

# 5. Test complet avec focus
python gridsearch_local.py

# 6. Analyse finale
python analyze_gridsearch.py output/gridsearch/run_20260128_170000

# 7. Lire les meilleurs scénarios
cat output/gridsearch/run_20260128_170000/test_015/scenario.json

# 8. Appliquer config optimale dans main_local.py
```

## 🎓 Comprendre les Résultats

### Taux de Succès

- **100%** : Excellente stabilité
- **80-99%** : Bon, quelques échecs acceptables
- **<80%** : Configuration problématique

### Nombre de Mots

- Plus de mots ≠ meilleure qualité
- Vérifier cohérence narrative
- Comparer avec durée cible

### Variabilité

Tests multiples avec même config :
- Variabilité haute → température élevée
- Variabilité basse → température faible

## 🔗 Ressources

- **Ollama Docs** : https://github.com/ollama/ollama/blob/main/docs/modelfile.md
- **Qwen3 Guide** : https://qwen.readthedocs.io/
- **LLM Parameters** : https://platform.openai.com/docs/api-reference/chat/create

## 🐛 Dépannage

### "Tous les tests échouent"

- Vérifier Ollama : `ollama list`
- Vérifier connexion : `python check_ollama.py`
- Augmenter timeout dans `main_local.py`

### "Résultats trop similaires"

- Augmenter écart entre valeurs de température
- Tester valeurs extrêmes (0.1, 1.0)

### "Tests trop longs"

- Mode `--quick`
- Prompt plus court
- Moins de parties narratives

### "Erreur de mémoire"

- Réduire `max_tokens`
- Fermer autres applications
- Redémarrer Ollama

---

**🎯 Bon gridsearch ! Trouvez votre configuration idéale !**
