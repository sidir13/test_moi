# Script PowerShell pour setup rapide du projet avec UV
# Usage: .\setup_project.ps1

Write-Host "`n================================================================================`n" -ForegroundColor Cyan
Write-Host "🎙️  MÉMOIRE DES TERRITOIRES - Setup avec UV" -ForegroundColor Cyan
Write-Host "`n================================================================================`n" -ForegroundColor Cyan

# 1. Vérifier si uv est installé
Write-Host "Étape 1: Vérification de uv..." -ForegroundColor Yellow
try {
    $uvVersion = uv --version
    Write-Host "✓ uv installé: $uvVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ uv non trouvé. Installation..." -ForegroundColor Red
    Write-Host "Installation de uv..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    
    # Recharger PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    Write-Host "✓ uv installé" -ForegroundColor Green
}

# 2. Créer environnement virtuel
Write-Host "`nÉtape 2: Création de l'environnement virtuel..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "⚠ .venv existe déjà" -ForegroundColor Yellow
    $response = Read-Host "Supprimer et recréer? (o/N)"
    if ($response -eq "o" -or $response -eq "O") {
        Remove-Item -Recurse -Force .venv
        uv venv
        Write-Host "✓ Environnement recréé" -ForegroundColor Green
    }
} else {
    uv venv
    Write-Host "✓ Environnement créé" -ForegroundColor Green
}

# 3. Activer environnement
Write-Host "`nÉtape 3: Activation de l'environnement..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
Write-Host "✓ Environnement activé" -ForegroundColor Green

# 4. Installer dépendances
Write-Host "`nÉtape 4: Installation des dépendances..." -ForegroundColor Yellow
uv pip install -r requirements.txt
Write-Host "✓ Dépendances installées" -ForegroundColor Green

# 5. Créer .env si n'existe pas
Write-Host "`nÉtape 5: Configuration .env..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env" -ErrorAction SilentlyContinue
    Write-Host "✓ Fichier .env créé (à configurer)" -ForegroundColor Green
    Write-Host "  → Éditez .env et ajoutez votre clé OpenRouter" -ForegroundColor Yellow
} else {
    Write-Host "✓ .env existe déjà" -ForegroundColor Green
}

# 6. Créer dossiers nécessaires
Write-Host "`nÉtape 6: Création des dossiers..." -ForegroundColor Yellow
$folders = @(
    "output/scenarios",
    "output/timelines",
    "output/structures",
    "logs"
)

foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
    }
}
Write-Host "✓ Dossiers créés" -ForegroundColor Green

# 7. Test de l'installation
Write-Host "`nÉtape 7: Test de l'installation..." -ForegroundColor Yellow
try {
    python -c "import anthropic, rich, typer, requests; print('✓ Imports OK')"
    Write-Host "✓ Tous les modules importés" -ForegroundColor Green
} catch {
    Write-Host "✗ Erreur d'import" -ForegroundColor Red
    exit 1
}

# 8. Résumé
Write-Host "`n================================================================================`n" -ForegroundColor Cyan
Write-Host "✅ INSTALLATION COMPLÈTE !`n" -ForegroundColor Green
Write-Host "Prochaines étapes:`n" -ForegroundColor Cyan

Write-Host "1. Configurer .env avec votre clé OpenRouter:" -ForegroundColor White
Write-Host "   notepad .env`n" -ForegroundColor Gray

Write-Host "2. Lancer avec Docker:" -ForegroundColor White
Write-Host "   make refresh`n" -ForegroundColor Gray

Write-Host "3. Ou via CLI:" -ForegroundColor White
Write-Host "   python cli.py generate `"Votre prompt`"`n" -ForegroundColor Gray

Write-Host "4. Lancer les tests:" -ForegroundColor White
Write-Host "   pytest`n" -ForegroundColor Gray

Write-Host "================================================================================`n" -ForegroundColor Cyan
