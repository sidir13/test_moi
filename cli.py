"""
Command-line interface for Mémoire des Territoires.
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.syntax import Syntax

from orchestrator import ScenarioMakerOrchestrator

app = typer.Typer(
    name="memoire-territoires",
    help="Générateur d'archives audio historiques enrichies",
    add_completion=False
)

console = Console()


@app.command()
def generate(
    prompt: Optional[str] = typer.Argument(None, help="Prompt en langage naturel"),
    mode: str = typer.Option("simple", "--mode", "-m", help="Mode: simple ou expert"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Fichier config JSON (mode expert)"),
    output: str = typer.Option("./output", "--output", "-o", help="Dossier de sortie"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Clé API Anthropic"),
    log_level: str = typer.Option("INFO", "--log-level", help="Niveau de log"),
    no_confirm: bool = typer.Option(False, "--yes", "-y", help="Ne pas demander confirmation")
):
    """
    Génère des scénarios audio historiques.
    
    Exemples:
    
    Mode simple (prompt):
        memoire-territoires generate "Un documentaire de 5 minutes sur la grève des dockers de 1905"
    
    Mode expert (fichier config):
        memoire-territoires generate --mode expert --config ma_config.json
    """
    console.print(Panel.fit(
        "[bold cyan]Mémoire des Territoires[/bold cyan]\n"
        "Générateur d'Archives Audio Historiques",
        border_style="cyan"
    ))
    
    # Check API key
    if not api_key and not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]Erreur: Clé API Anthropic requise[/red]")
        console.print("Définissez ANTHROPIC_API_KEY dans .env ou utilisez --api-key")
        raise typer.Exit(code=1)
    
    # Get user input
    user_input = None
    
    if mode == "simple":
        if not prompt:
            console.print("\n[cyan]Mode simple:[/cyan] Décrivez ce que vous voulez créer\n")
            prompt = Prompt.ask("[bold]Votre demande[/bold]")
        
        user_input = prompt
        console.print(f"\n[dim]Prompt: {prompt}[/dim]\n")
        
    elif mode == "expert":
        if not config:
            console.print("[red]Erreur: Mode expert nécessite --config[/red]")
            raise typer.Exit(code=1)
        
        config_path = Path(config)
        if not config_path.exists():
            console.print(f"[red]Erreur: Fichier config non trouvé: {config}[/red]")
            raise typer.Exit(code=1)
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_input = json.load(f)
            console.print(f"\n[dim]Configuration chargée depuis: {config}[/dim]\n")
        except Exception as e:
            console.print(f"[red]Erreur lecture config: {e}[/red]")
            raise typer.Exit(code=1)
    
    else:
        console.print(f"[red]Erreur: Mode inconnu: {mode}[/red]")
        raise typer.Exit(code=1)
    
    # Initialize orchestrator
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Initialisation...", total=None)
            orchestrator = ScenarioMakerOrchestrator(
                api_key=api_key,
                log_level=log_level
            )
            progress.update(task, completed=True)
        
        console.print("[green]✓[/green] Orchestrateur initialisé\n")
        
    except Exception as e:
        console.print(f"[red]Erreur initialisation: {e}[/red]")
        raise typer.Exit(code=1)
    
    # Generate scenarios
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Génération en cours...", total=None)
        
        try:
            result = orchestrator.create_scenarios(
                user_input=user_input,
                mode=mode,
                output_dir=output
            )
            progress.update(task, completed=True)
            
        except Exception as e:
            progress.update(task, completed=True)
            console.print(f"\n[red]Erreur génération: {e}[/red]")
            raise typer.Exit(code=1)
    
    # Display results
    if result['status'] == 'success':
        console.print("\n[green]✓ Génération réussie![/green]\n")
        
        # Show summary
        console.print(Panel(
            result['summary'],
            title="Configuration Générée",
            border_style="green"
        ))
        
        # Show validation warnings
        if result['validation']['warnings']:
            console.print("\n[yellow]⚠ Avertissements:[/yellow]")
            for warning in result['validation']['warnings']:
                console.print(f"  • {warning}")
        
        # Show metadata
        console.print(f"\n[dim]Temps de génération: {result['generation_time']:.2f}s[/dim]")
        console.print(f"[dim]{result['message']}[/dim]\n")
        
        # Offer to show full config
        if not no_confirm:
            if Confirm.ask("Afficher la configuration complète?", default=False):
                config_json = json.dumps(result['config'], indent=2, ensure_ascii=False)
                syntax = Syntax(config_json, "json", theme="monokai", line_numbers=True)
                console.print("\n")
                console.print(syntax)
        
    else:
        console.print(f"\n[red]✗ Erreur: {result.get('error', 'Unknown error')}[/red]")
        raise typer.Exit(code=1)


@app.command()
def validate(
    config_path: str = typer.Argument(..., help="Chemin vers le fichier de configuration")
):
    """
    Valide un fichier de configuration sans générer de scénarios.
    """
    console.print("[cyan]Validation de configuration[/cyan]\n")
    
    path = Path(config_path)
    if not path.exists():
        console.print(f"[red]Erreur: Fichier non trouvé: {config_path}[/red]")
        raise typer.Exit(code=1)
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Basic validation
        console.print("[green]✓[/green] JSON valide")
        
        # Check structure
        if 'scenario_config' in config:
            console.print("[green]✓[/green] Structure valide")
            
            # Show key parameters
            gen_params = config.get('scenario_config', {}).get('generation_parameters', {})
            
            table = Table(title="Paramètres Principaux")
            table.add_column("Paramètre", style="cyan")
            table.add_column("Valeur", style="white")
            
            for key in ['forme', 'duree', 'ton', 'public_cible']:
                if key in gen_params:
                    value = gen_params[key].get('value', 'N/A')
                    table.add_row(key, str(value))
            
            console.print("\n")
            console.print(table)
            console.print("\n[green]Configuration valide![/green]")
        else:
            console.print("[yellow]⚠ Structure inhabituelle (clé 'scenario_config' manquante)[/yellow]")
        
    except json.JSONDecodeError as e:
        console.print(f"[red]Erreur JSON: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Erreur: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def list_skills():
    """
    Liste tous les agents et skills disponibles.
    """
    console.print("[cyan]Agents et Skills Disponibles[/cyan]\n")
    
    try:
        orchestrator = ScenarioMakerOrchestrator(log_level="ERROR")
        skills = orchestrator.list_available_skills()
        
        # Agents table
        agents_table = Table(title="Agents", show_header=True)
        agents_table.add_column("Nom", style="cyan")
        agents_table.add_column("Statut", style="green")
        
        for agent in skills['agents']:
            agents_table.add_row(agent, "✓ Chargé")
        
        console.print(agents_table)
        console.print()
        
        # Skills table
        if skills['skills']:
            skills_table = Table(title="Skills", show_header=True)
            skills_table.add_column("Nom", style="cyan")
            skills_table.add_column("Statut", style="green")
            
            for skill in skills['skills']:
                skills_table.add_row(skill, "✓ Chargé")
            
            console.print(skills_table)
        else:
            console.print("[dim]Aucun skill chargé[/dim]")
        
    except Exception as e:
        console.print(f"[red]Erreur: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def version():
    """Affiche la version du système."""
    console.print("[cyan]Mémoire des Territoires[/cyan]")
    console.print("Version: 1.0.0")
    console.print("Pipeline: v1 (Agent 0 uniquement)")


if __name__ == "__main__":
    app()
