"""
Script pour vérifier la connexion et les modèles Groq disponibles.
"""

import os
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from dotenv import load_dotenv

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.groq_client import GroqClientWrapper, get_available_groq_models, test_groq_connection

console = Console()


def main():
    """Vérifie la connexion à Groq et liste les modèles disponibles."""
    
    console.print(Panel(
        "[bold cyan]🔍 Vérification de Groq API[/bold cyan]",
        border_style="cyan"
    ))
    
    # Charger les variables d'environnement
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    
    # Vérifier la clé API
    console.print("\n[yellow]1. Vérification de la clé API...[/yellow]")
    if api_key:
        console.print(f"   ✅ GROQ_API_KEY trouvée : {api_key[:10]}...{api_key[-4:]}")
    else:
        console.print("   ❌ GROQ_API_KEY non trouvée dans .env")
        console.print("\n[red]Ajoutez votre clé dans le fichier .env :[/red]")
        console.print("   GROQ_API_KEY=votre_clé_ici")
        return
    
    # Lister les modèles disponibles
    console.print("\n[yellow]2. Modèles Groq disponibles :[/yellow]")
    models = get_available_groq_models()
    
    table = Table(title="Modèles Groq", show_header=True, header_style="bold magenta")
    table.add_column("Alias", style="cyan", width=15)
    table.add_column("ID Modèle", style="yellow", width=30)
    table.add_column("Description", style="green")
    
    model_descriptions = {
        "llama-3.1-8b": "🚀 Rapide, 8B params",
        "llama-3.1-70b": "💪 Puissant, 70B params",
        "llama-3.2-90b": "🔥 Très puissant, 90B params",
        "llama-3.3-70b": "⚡ Nouvelle version, 70B",
        "mixtral-8x7b": "🎯 Mixtral, 8x7B MoE",
        "gemma-7b": "📦 Compact, 7B params",
        "gemma2-9b": "📦 Gemma v2, 9B params",
    }
    
    for alias, model_id in models.items():
        description = model_descriptions.get(alias, "")
        table.add_row(alias, model_id, description)
    
    console.print(table)
    
    # Tester la connexion
    console.print("\n[yellow]3. Test de connexion...[/yellow]")
    console.print("   [dim]Test avec llama-3.1-8b (rapide)...[/dim]")
    
    if test_groq_connection(api_key=api_key, model="llama-3.1-8b"):
        console.print("   ✅ [bold green]Connexion réussie ![/bold green]")
        console.print("\n[green]Tout est prêt ! Vous pouvez maintenant :[/green]")
        console.print("   • [cyan]python main_local.py --provider groq[/cyan]")
        console.print("   • [cyan]python gridsearch_groq.py --mode standard[/cyan]")
    else:
        console.print("   ❌ [bold red]Échec de la connexion[/bold red]")
        console.print("\n[red]Vérifiez :[/red]")
        console.print("   • Votre clé API est valide")
        console.print("   • Vous avez accès à l'API Groq")
        console.print("   • Votre connexion internet fonctionne")


if __name__ == "__main__":
    main()
