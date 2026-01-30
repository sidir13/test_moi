# 🚀 Guide Groq - Tests avec API Groq

Guide complet pour utiliser Groq API avec le système Mémoire des Territoires.

## 📋 Table des Matières

- [Qu'est-ce que Groq ?](#quest-ce-que-groq-)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage Simple](#usage-simple)
- [Gridsearch Multi-Modèles](#gridsearch-multi-modèles)
- [Modèles Disponibles](#modèles-disponibles)
- [Comparaison Groq vs Ollama](#comparaison-groq-vs-ollama)

---

## Qu'est-ce que Groq ?

**Groq** est une plateforme d'inférence LLM ultra-rapide utilisant des **LPU** (Language Processing Units).

### ✅ Avantages

- **⚡ Extrêmement rapide** : Jusqu'à 10x plus rapide que les GPU traditionnels
- **🌐 API Cloud** : Pas besoin d'installation locale
- **🆓 Gratuit** : Tier gratuit généreux (quota quotidien)
- **🎯 Simple** : API compatible OpenAI
- **🔥 Modèles puissants** : Llama 3.1, Mixtral, Gemma

### ❌ Limitations

- **🌍 Connexion internet requise**
- **📊 Quotas** : Limites de requêtes (gratuit : ~30 req/min)
- **🔒 Données envoyées** : API cloud (vs local avec Ollama)

---

## Installation

### 1. Installer les Dépendances

```bash
pip install requests python-dotenv rich
```

ou avec uv :

```bash
uv pip install requests python-dotenv rich
```

### 2. Obtenir une Clé API Groq

1. Allez sur [https://console.groq.com](https://console.groq.com)
2. Créez un compte (gratuit)
3. Allez dans **API Keys**
4. Créez une nouvelle clé
5. Copiez la clé (elle commence par `gsk_`)

### 3. Configurer la Clé

Ajoutez votre clé dans le fichier `.env` :

```bash
GROQ_API_KEY=gsk_votre_clé_ici
```

### 4. Vérifier la Connexion

```bash
python check_groq.py
```

Vous devriez voir :

```
✅ GROQ_API_KEY trouvée : gsk_xxxxx...xxxx
✅ Connexion réussie !
```

---

## Configuration

### Fichier `.env`

```bash
# Clé API Groq
GROQ_API_KEY=gsk_votre_clé_ici

# (Optionnel) Modèle par défaut
GROQ_DEFAULT_MODEL=llama-3.1-8b
```

### Modifier le Modèle

Dans `main_local.py`, section `GROQ_CONFIG` :

```python
GROQ_CONFIG = {
    'model': 'llama-3.1-70b',  # Changez ici
    'timeout': 300
}
```

---

## Usage Simple

### Mode Interactif

```bash
python main_local.py --provider groq
```

Le script vous demandera votre prompt.

### Avec Prompt Direct

```bash
python main_local.py --provider groq "Un documentaire de 4 minutes sur la grève des mineurs de 1948"
```

### Avec Modèle Spécifique

```bash
python main_local.py --provider groq --model llama-3.1-70b "Votre prompt ici"
```

### Exemples Complets

**Documentaire historique** :
```bash
python main_local.py --provider groq --model llama-3.1-70b "Un documentaire dramatique de 5 minutes sur la bataille de Verdun"
```

**Récit intimiste** :
```bash
python main_local.py --provider groq --model mixtral-8x7b "Un récit contemplatif sur la vie des dockers au début du 20ème siècle"
```

**Témoignage** :
```bash
python main_local.py --provider groq "Un témoignage émotionnel de 3 minutes sur les conditions de travail dans les mines"
```

---

## Gridsearch Multi-Modèles

### Qu'est-ce que le Gridsearch Groq ?

Le script `gridsearch_groq.py` teste automatiquement :
- ✅ **Plusieurs modèles Groq** (Llama, Mixtral, Gemma)
- ✅ **Différents paramètres JSON** (ton, forme, public, densité, style)
- ✅ **Génération de scénarios complets** pour chaque combinaison

### Modes de Test

| Mode | Tests | Modèles | Combinaisons | Durée |
|------|-------|---------|--------------|-------|
| `--quick` | 4 | 2 | 2 | ~10-15 min |
| `--standard` | 12 | 2 | 6 | ~30-40 min |
| `--full` | 32 | 4 | 8 | ~2-3 heures |

### Lancer le Gridsearch

**Mode standard (recommandé)** :
```bash
python gridsearch_groq.py --mode standard
```

**Mode rapide (test)** :
```bash
python gridsearch_groq.py --mode quick
```

**Mode complet** :
```bash
python gridsearch_groq.py --mode full
```

### Choisir les Modèles

```bash
python gridsearch_groq.py --models llama-3.1-8b llama-3.1-70b mixtral-8x7b
```

### Prompt Personnalisé

```bash
python gridsearch_groq.py --prompt "Créez un récit sur la révolution industrielle"
```

### Analyser les Résultats

Après le gridsearch :

```bash
python analyze_gridsearch.py --input output/gridsearch_groq/run_XXXXXXXX_XXXXXX
```

### Structure des Résultats

```
output/gridsearch_groq/
└── run_20260130_143000/
    ├── gridsearch_results.json       # Résultats globaux
    ├── test_001_llama-3.1-8b_neutre_informatif_documentaire/
    │   ├── config.json
    │   ├── structure.json
    │   ├── scenario.json
    │   └── timeline.json
    ├── test_002_llama-3.1-8b_dramatique_immersif_recit_narratif/
    │   └── ...
    └── ...
```

---

## Modèles Disponibles

### Llama 3.1 - 8B (Rapide)

**Alias** : `llama-3.1-8b`  
**ID Complet** : `llama-3.1-8b-instant`

- ⚡ **Très rapide** (~50-100 tokens/s)
- 📦 **Compact** : 8 milliards de paramètres
- 💰 **Gratuit** : Idéal pour tests et prototypes
- ✅ **Usage** : Tests rapides, itérations

```bash
python main_local.py --provider groq --model llama-3.1-8b "Votre prompt"
```

---

### Llama 3.1 - 70B (Puissant)

**Alias** : `llama-3.1-70b`  
**ID Complet** : `llama-3.1-70b-versatile`

- 💪 **Puissant** : 70 milliards de paramètres
- 🎯 **Qualité** : Génération de haute qualité
- ⚡ **Rapide** : Grâce aux LPU Groq
- ✅ **Usage** : Production, scénarios finaux

```bash
python main_local.py --provider groq --model llama-3.1-70b "Votre prompt"
```

---

### Llama 3.3 - 70B (Dernière Version)

**Alias** : `llama-3.3-70b`  
**ID Complet** : `llama-3.3-70b-versatile`

- 🔥 **Nouveau** : Version améliorée de Llama 3.1
- 💪 **Puissant** : 70B paramètres
- 📚 **Meilleure compréhension** : Instructions complexes
- ✅ **Usage** : Scénarios complexes, multi-agents

```bash
python main_local.py --provider groq --model llama-3.3-70b "Votre prompt"
```

---

### Mixtral 8x7B (Alternatif)

**Alias** : `mixtral-8x7b`  
**ID Complet** : `mixtral-8x7b-32768`

- 🎯 **Architecture MoE** : Mixture of Experts
- 📖 **Contexte long** : 32k tokens
- 🌍 **Multilingue** : Excellent en français
- ✅ **Usage** : Scénarios longs, multilingues

```bash
python main_local.py --provider groq --model mixtral-8x7b "Votre prompt"
```

---

### Gemma 2 - 9B (Compact)

**Alias** : `gemma2-9b`  
**ID Complet** : `gemma2-9b-it`

- 📦 **Compact** : 9B paramètres
- ⚡ **Rapide** : Inférence très rapide
- 🎓 **Google** : Développé par Google DeepMind
- ✅ **Usage** : Tests, prototypes, scénarios courts

```bash
python main_local.py --provider groq --model gemma2-9b "Votre prompt"
```

---

## Comparaison Groq vs Ollama

| Critère | Groq | Ollama |
|---------|------|--------|
| **Vitesse** | ⚡⚡⚡ Très rapide | ⚡⚡ Rapide |
| **Installation** | ✅ Aucune | ❌ Installation locale |
| **Internet** | ❌ Requis | ✅ Pas nécessaire |
| **Coût** | 🆓 Gratuit (quotas) | 🆓 Totalement gratuit |
| **Confidentialité** | ⚠️ API cloud | ✅ 100% local |
| **Modèles** | Llama, Mixtral, Gemma | Tous (Qwen, Llama, Mistral...) |
| **Qualité** | ⭐⭐⭐⭐ Excellente | ⭐⭐⭐ Bonne |
| **Production** | ✅ Prêt | ⚠️ Tests/dev |

### Quand utiliser Groq ?

✅ **Tests rapides** : Itérations et prototypage  
✅ **Qualité élevée** : Scénarios finaux  
✅ **Pas de GPU** : Pas de matériel puissant  
✅ **Comparaisons** : Tester plusieurs modèles rapidement  

### Quand utiliser Ollama ?

✅ **Confidentialité** : Données sensibles  
✅ **Hors ligne** : Pas de connexion internet  
✅ **Gratuit illimité** : Pas de quotas  
✅ **Personnalisation** : Fine-tuning, modèles custom  

---

## Paramètres JSON Testés par Gridsearch

Le gridsearch teste différentes combinaisons de :

### 1. Ton (`ton`)

- `neutre_informatif` : Objectif, factuel
- `emotionnel_empathique` : Touchant, humain
- `dramatique_immersif` : Intense, captivant
- `contemplatif_poetique` : Réflexif, artistique

### 2. Forme (`forme`)

- `documentaire` : Format documentaire classique
- `reportage` : Style reportage journalistique
- `temoignage_direct` : Première personne
- `recit_narratif` : Narration storytelling

### 3. Public Cible (`public_cible`)

- `grand_public` : Accessible à tous
- `scolaire_secondaire` : Pour lycéens
- `expert_historien` : Niveau académique

### 4. Densité Narrative (`densite_narrative`)

- `sparse` : Peu d'infos, beaucoup de silences
- `equilibree` : Balance info/ambiance
- `dense` : Beaucoup d'informations

### 5. Style Linguistique (`style_linguistique`)

- `moderne_accessible` : Français contemporain
- `authentique_epoque` : Vocabulaire d'époque
- `litteraire_soigne` : Style littéraire

---

## Dépannage

### Erreur : "GROQ_API_KEY not found"

```bash
# Vérifiez votre .env
cat .env | grep GROQ

# Si vide, ajoutez :
echo "GROQ_API_KEY=gsk_votre_clé" >> .env
```

### Erreur : "Rate limit exceeded"

Vous avez atteint le quota gratuit. Solutions :

1. **Attendez** : Les quotas se réinitialisent toutes les heures
2. **Utilisez `--mode quick`** : Moins de tests
3. **Passez à Ollama** : Pour tests illimités locaux

### Erreur : "Timeout"

Augmentez le timeout dans `main_local.py` :

```python
GROQ_CONFIG = {
    'model': 'llama-3.1-70b',
    'timeout': 600  # 10 minutes au lieu de 5
}
```

### Connexion lente

Groq est très rapide, mais :
- Vérifiez votre connexion internet
- Essayez un modèle plus petit (`llama-3.1-8b`)
- Testez à un autre moment (moins de charge serveur)

---

## Workflow Recommandé

### 1. Tests Rapides avec Groq 8B

```bash
# Itérations rapides
python main_local.py --provider groq --model llama-3.1-8b "Test prompt"
```

### 2. Gridsearch pour Optimisation

```bash
# Tester différentes configurations
python gridsearch_groq.py --mode standard
```

### 3. Production avec Groq 70B

```bash
# Génération finale haute qualité
python main_local.py --provider groq --model llama-3.1-70b "Prompt final validé"
```

### 4. Comparaison Ollama vs Groq

```bash
# Test Ollama
python main_local.py "Même prompt"

# Test Groq
python main_local.py --provider groq "Même prompt"

# Comparer les résultats dans output/local_tests/
```

---

## Ressources

- **Console Groq** : https://console.groq.com
- **Documentation Groq** : https://console.groq.com/docs
- **Modèles disponibles** : https://console.groq.com/docs/models
- **Pricing** : https://console.groq.com/settings/billing

---

## Résumé des Commandes

```bash
# Vérifier Groq
python check_groq.py

# Test simple
python main_local.py --provider groq "Votre prompt"

# Avec modèle spécifique
python main_local.py --provider groq --model llama-3.1-70b "Prompt"

# Gridsearch rapide
python gridsearch_groq.py --mode quick

# Gridsearch standard
python gridsearch_groq.py --mode standard

# Analyser les résultats
python analyze_gridsearch.py --input output/gridsearch_groq/run_XXXXXX
```

---

**Prêt à tester Groq ? 🚀**

Commencez par :
```bash
python check_groq.py
python main_local.py --provider groq
```
