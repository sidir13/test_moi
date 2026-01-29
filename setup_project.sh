#!/bin/bash
# Script Bash pour setup rapide du projet avec UV
# Usage: ./setup_project.sh

echo ""
echo "================================================================================"
echo "🎙️  MÉMOIRE DES TERRITOIRES - Setup avec UV"
echo "================================================================================"
echo ""

# 1. Vérifier si uv est installé
echo "Étape 1: Vérification de uv..."
if command -v uv &> /dev/null; then
    echo "✓ uv installé: $(uv --version)"
else
    echo "✗ uv non trouvé. Installation..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Recharger PATH
    export PATH="$HOME/.cargo/bin:$PATH"
    
    echo "✓ uv installé"
fi

# 2. Créer environnement virtuel
echo ""
echo "Étape 2: Création de l'environnement virtuel..."
if [ -d ".venv" ]; then
    echo "⚠ .venv existe déjà"
    read -p "Supprimer et recréer? (o/N) " response
    if [ "$response" = "o" ] || [ "$response" = "O" ]; then
        rm -rf .venv
        uv venv
        echo "✓ Environnement recréé"
    fi
else
    uv venv
    echo "✓ Environnement créé"
fi

# 3. Activer environnement
echo ""
echo "Étape 3: Activation de l'environnement..."
source .venv/bin/activate
echo "✓ Environnement activé"

# 4. Installer dépendances
echo ""
echo "Étape 4: Installation des dépendances..."
uv pip install -r requirements.txt
echo "✓ Dépendances installées"

# 5. Créer .env si n'existe pas
echo ""
echo "Étape 5: Configuration .env..."
if [ ! -f ".env" ]; then
    cp .env.example .env 2>/dev/null || true
    echo "✓ Fichier .env créé (à configurer)"
    echo "  → Éditez .env et ajoutez votre clé API"
else
    echo "✓ .env existe déjà"
fi

# 6. Créer dossiers nécessaires
echo ""
echo "Étape 6: Création des dossiers..."
mkdir -p output/local_tests output/scenarios output/timelines output/exports logs
echo "✓ Dossiers créés"

# 7. Test de l'installation
echo ""
echo "Étape 7: Test de l'installation..."
if python -c "import anthropic, rich, typer, requests; print('✓ Imports OK')" 2>/dev/null; then
    echo "✓ Tous les modules importés"
else
    echo "✗ Erreur d'import"
    exit 1
fi

# 8. Résumé
echo ""
echo "================================================================================"
echo "✅ INSTALLATION COMPLÈTE !"
echo ""
echo "Prochaines étapes:"
echo ""
echo "1. Configurer .env avec votre clé API:"
echo "   nano .env"
echo ""
echo "2. Pour tests locaux (Ollama):"
echo "   python check_ollama.py"
echo "   python main_local.py"
echo ""
echo "3. Pour production (Claude):"
echo "   python cli.py generate \"Votre prompt\""
echo ""
echo "4. Lancer les tests:"
echo "   pytest"
echo ""
echo "Documentation:"
echo "   - SETUP_UV.md"
echo "   - QUICKSTART_LOCAL.md"
echo "   - README_IMPLEMENTATION.md"
echo ""
echo "================================================================================"
echo ""
