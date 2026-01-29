# 🚀 Installation avec UV

Guide d'installation ultra-rapide avec `uv`, le gestionnaire de packages Python moderne.

## Pourquoi UV ?

- ⚡ **10-100x plus rapide** que pip
- 🔒 **Lock files** automatiques
- 📦 **Gestion d'environnements** intégrée
- 🎯 **Compatible** avec pip et requirements.txt

## Installation UV

### Windows (PowerShell)

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### macOS/Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Vérification

```bash
uv --version
```

## Setup du Projet

### Option 1 : Environnement complet (Recommandé)

```bash
# Créer environnement et installer tout
uv venv
uv pip install -e .

# Activer l'environnement
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

### Option 2 : Installation rapide sans environnement

```bash
# Installer directement avec uv (sans venv)
uv pip install -r requirements.txt
```

### Option 3 : Développement (avec outils de dev)

```bash
# Créer environnement
uv venv

# Activer
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate    # macOS/Linux

# Installer avec dépendances de dev
uv pip install -e ".[dev]"
```

## Test de l'Installation

```bash
# Vérifier les imports
python -c "import anthropic, rich, typer; print('✅ OK')"

# Vérifier Ollama (pour tests locaux)
python check_ollama.py

# Lancer les tests
pytest
```

## Utilisation

### Tests Locaux (Ollama)

```bash
python main_local.py
```

### Production (Claude)

```bash
# Créer .env avec votre clé
echo "ANTHROPIC_API_KEY=sk-ant-votre-clé" > .env

# Lancer
python cli.py generate "Votre prompt ici"
```

## Commandes UV Utiles

### Installation

```bash
# Installer package
uv pip install nom-package

# Installer depuis requirements.txt
uv pip install -r requirements.txt

# Installer le projet en mode éditable
uv pip install -e .

# Avec extras (dev, audio, etc.)
uv pip install -e ".[dev]"
uv pip install -e ".[audio]"
```

### Environnements

```bash
# Créer environnement
uv venv

# Créer avec version Python spécifique
uv venv --python 3.11

# Supprimer environnement
rm -rf .venv  # ou rmdir /s .venv sur Windows
```

### Mise à jour

```bash
# Mettre à jour un package
uv pip install --upgrade nom-package

# Mettre à jour toutes les dépendances
uv pip install --upgrade -r requirements.txt
```

### Information

```bash
# Lister packages installés
uv pip list

# Afficher info sur un package
uv pip show nom-package

# Générer requirements.txt
uv pip freeze > requirements-lock.txt
```

## Structure avec UV

```
memoire-territoires/
├── .venv/              # Environnement virtuel (créé par uv venv)
├── pyproject.toml      # Configuration moderne du projet
├── requirements.txt    # Dépendances (compatibilité pip)
├── .env               # Variables d'environnement (ne pas commit)
└── ...
```

## Dépendances du Projet

### Core (toujours installées)

- `anthropic` - API Claude
- `pydantic` - Validation de données
- `rich` - Interface CLI belle
- `typer` - CLI framework
- `requests` - HTTP pour Ollama
- `python-dotenv` - Variables d'environnement

### Dev (optionnelles)

```bash
uv pip install -e ".[dev]"
```

- `pytest` - Tests
- `black` - Formatage
- `ruff` - Linting

### Audio (optionnelles)

```bash
uv pip install -e ".[audio]"
```

- `openai-whisper` - Transcription audio

## Résolution de Problèmes

### "uv: command not found"

```bash
# Réinstaller uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Redémarrer le terminal
```

### "Cannot find Python"

```bash
# Spécifier la version Python
uv venv --python 3.11

# Ou utiliser Python système
uv venv --python python3
```

### "Module not found" après installation

```bash
# Vérifier que l'environnement est activé
which python  # doit pointer vers .venv/bin/python

# Réinstaller si nécessaire
uv pip install --force-reinstall -e .
```

### Conflits de dépendances

```bash
# Nettoyer et réinstaller
rm -rf .venv
uv venv
uv pip install -e .
```

## Migration depuis pip

Si vous utilisez déjà pip :

```bash
# 1. Sauvegarder l'existant
pip freeze > old-requirements.txt

# 2. Créer nouvel environnement avec uv
uv venv
source .venv/bin/activate  # ou .venv\Scripts\Activate.ps1

# 3. Installer avec uv
uv pip install -r requirements.txt

# 4. Tester
python main_local.py
```

## Comparaison Performances

| Action | pip | uv | Gain |
|--------|-----|-----|------|
| Installer projet | 45s | 2s | **22x** |
| Créer venv | 5s | 0.1s | **50x** |
| Résoudre dépendances | 30s | 1s | **30x** |

## Scripts Rapides

### Setup complet (Windows PowerShell)

```powershell
# Installer uv
irm https://astral.sh/uv/install.ps1 | iex

# Setup projet
uv venv
.venv\Scripts\Activate.ps1
uv pip install -e .

# Tester
python check_ollama.py
python main_local.py
```

### Setup complet (macOS/Linux)

```bash
# Installer uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup projet
uv venv
source .venv/bin/activate
uv pip install -e .

# Tester
python check_ollama.py
python main_local.py
```

## Liens

- **uv** : https://github.com/astral-sh/uv
- **Documentation** : https://docs.astral.sh/uv/
- **Blog Astral** : https://astral.sh/blog

---

**Installation complète en ~30 secondes avec uv ! ⚡**
