"""
Gridsearch pour tester différents modèles Groq et paramètres de configuration JSON.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.panel import Panel

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.groq_client import GroqClientWrapper, get_available_groq_models
from orchestrator import ScenarioMakerOrchestrator
from models.config_models import ScenarioConfig

console = Console()


# Configuration des modèles Groq à tester
GROQ_MODELS = {
    "llama-3.1-8b": "llama-3.1-8b-instant",      # Rapide
    "llama-3.1-70b": "llama-3.1-70b-versatile",  # Puissant
    "mixtral-8x7b": "mixtral-8x7b-32768",        # Alternatif
    "gemma2-9b": "gemma2-9b-it",                 # Compact
}

# Paramètres JSON à tester
JSON_PARAMETERS = {
    "ton": [
        "neutre_informatif",
        "emotionnel_empathique",
        "dramatique_immersif",
        "contemplatif_poetique"
    ],
    "forme": [
        "documentaire",
        "reportage",
        "temoignage_direct",
        "recit_narratif"
    ],
    "public_cible": [
        "grand_public",
        "scolaire_secondaire",
        "expert_historien"
    ],
    "densite_narrative": [
        "sparse",      # Peu d'informations, beaucoup de silences
        "equilibree",  # Balance info/ambiance
        "dense"        # Beaucoup d'informations
    ],
    "style_linguistique": [
        "moderne_accessible",
        "authentique_epoque",
        "litteraire_soigne"
    ]
}


def create_test_config(
    base_config: Dict[str, Any],
    ton: str,
    forme: str,
    public: str,
    densite: str,
    style: str
) -> Dict[str, Any]:
    """
    Crée une configuration de test avec les paramètres spécifiés.
    
    Args:
        base_config: Configuration de base
        ton: Ton narratif
        forme: Forme narrative
        public: Public cible
        densite: Densité narrative
        style: Style linguistique
    
    Returns:
        Configuration modifiée
    """
    config = base_config.copy()
    
    # Modifier les paramètres de génération
    config["scenario_config"]["generation_parameters"]["ton"]["value"] = ton
    config["scenario_config"]["generation_parameters"]["forme"]["value"] = forme
    config["scenario_config"]["generation_parameters"]["public_cible"]["value"] = public
    
    # Ajouter les nouveaux paramètres s'ils n'existent pas
    if "densite_narrative" not in config["scenario_config"]["generation_parameters"]:
        config["scenario_config"]["generation_parameters"]["densite_narrative"] = {}
    config["scenario_config"]["generation_parameters"]["densite_narrative"]["value"] = densite
    
    if "style_linguistique" not in config["scenario_config"]["generation_parameters"]:
        config["scenario_config"]["generation_parameters"]["style_linguistique"] = {}
    config["scenario_config"]["generation_parameters"]["style_linguistique"]["value"] = style
    
    return config


def run_gridsearch(
    models: List[str],
    prompt: str,
    output_dir: Path,
    mode: str = "standard"
) -> Dict[str, Any]:
    """
    Lance le gridsearch sur les modèles et paramètres JSON.
    
    Args:
        models: Liste des modèles Groq à tester
        prompt: Prompt de base pour tous les tests
        output_dir: Dossier de sortie
        mode: Mode de test (quick, standard, full)
    
    Returns:
        Résultats du gridsearch
    """
    # Charger la config par défaut
    with open("config/default_config.json", "r", encoding="utf-8") as f:
        base_config = json.load(f)
    
    # Définir les combinaisons selon le mode
    if mode == "quick":
        # 2 modèles × 2 tons = 4 tests
        test_models = models[:2]
        test_combinations = [
            ("neutre_informatif", "documentaire", "grand_public", "equilibree", "moderne_accessible"),
            ("dramatique_immersif", "recit_narratif", "grand_public", "dense", "litteraire_soigne"),
        ]
    elif mode == "standard":
        # 2 modèles × 6 combinaisons = 12 tests
        test_models = models[:2]
        test_combinations = [
            ("neutre_informatif", "documentaire", "grand_public", "sparse", "moderne_accessible"),
            ("neutre_informatif", "reportage", "scolaire_secondaire", "equilibree", "moderne_accessible"),
            ("emotionnel_empathique", "temoignage_direct", "grand_public", "equilibree", "authentique_epoque"),
            ("emotionnel_empathique", "recit_narratif", "grand_public", "dense", "litteraire_soigne"),
            ("dramatique_immersif", "documentaire", "grand_public", "dense", "authentique_epoque"),
            ("contemplatif_poetique", "recit_narratif", "expert_historien", "sparse", "litteraire_soigne"),
        ]
    else:  # full
        # 4 modèles × 8 combinaisons = 32 tests
        test_models = models
        test_combinations = [
            ("neutre_informatif", "documentaire", "grand_public", "sparse", "moderne_accessible"),
            ("neutre_informatif", "reportage", "scolaire_secondaire", "equilibree", "moderne_accessible"),
            ("emotionnel_empathique", "temoignage_direct", "grand_public", "equilibree", "authentique_epoque"),
            ("emotionnel_empathique", "recit_narratif", "grand_public", "dense", "litteraire_soigne"),
            ("dramatique_immersif", "documentaire", "grand_public", "dense", "authentique_epoque"),
            ("dramatique_immersif", "temoignage_direct", "scolaire_secondaire", "equilibree", "moderne_accessible"),
            ("contemplatif_poetique", "recit_narratif", "expert_historien", "sparse", "litteraire_soigne"),
            ("contemplatif_poetique", "documentaire", "grand_public", "equilibree", "authentique_epoque"),
        ]
    
    total_tests = len(test_models) * len(test_combinations)
    
    console.print(Panel(
        f"[bold cyan]Gridsearch Groq × Configuration JSON[/bold cyan]\n\n"
        f"Modèles : {len(test_models)}\n"
        f"Combinaisons JSON : {len(test_combinations)}\n"
        f"Total tests : {total_tests}",
        title="🔬 Configuration",
        border_style="cyan"
    ))
    
    results = {
        "run_id": output_dir.name,
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt,
        "mode": mode,
        "models": test_models,
        "total_tests": total_tests,
        "tests": []
    }
    
    test_num = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        
        task = progress.add_task(
            f"[cyan]Tests en cours...",
            total=total_tests
        )
        
        for model in test_models:
            for ton, forme, public, densite, style in test_combinations:
                test_num += 1
                
                progress.update(
                    task,
                    description=f"[cyan]Test {test_num}/{total_tests} - {model} - {ton}/{forme}"
                )
                
                try:
                    # Créer le client Groq
                    groq_client = GroqClientWrapper(model=model, timeout=300)
                    
                    # Créer la configuration de test
                    test_config = create_test_config(
                        base_config, ton, forme, public, densite, style
                    )
                    
                    # Créer l'orchestrateur avec le client Groq
                    orchestrator = ScenarioMakerOrchestrator(
                        client=groq_client,
                        config_path="config/default_config.json"
                    )
                    
                    # Générer le scénario
                    result = orchestrator.generate_scenario_simple(
                        user_prompt=prompt,
                        override_config=test_config["scenario_config"]
                    )
                    
                    # Sauvegarder les outputs
                    test_dir = output_dir / f"test_{test_num:03d}_{model.replace('.', '_')}_{ton}_{forme}"
                    test_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Sauvegarder config
                    with open(test_dir / "config.json", "w", encoding="utf-8") as f:
                        json.dump(test_config, f, indent=2, ensure_ascii=False)
                    
                    # Sauvegarder structure
                    with open(test_dir / "structure.json", "w", encoding="utf-8") as f:
                        json.dump(result["structure"], f, indent=2, ensure_ascii=False)
                    
                    # Sauvegarder scénario
                    with open(test_dir / "scenario.json", "w", encoding="utf-8") as f:
                        json.dump(result["scenario"], f, indent=2, ensure_ascii=False)
                    
                    # Sauvegarder timeline
                    with open(test_dir / "timeline.json", "w", encoding="utf-8") as f:
                        json.dump(result["timeline"], f, indent=2, ensure_ascii=False)
                    
                    # Enregistrer les résultats
                    test_result = {
                        "test_id": test_num,
                        "model": model,
                        "parameters": {
                            "ton": ton,
                            "forme": forme,
                            "public_cible": public,
                            "densite_narrative": densite,
                            "style_linguistique": style
                        },
                        "status": "success",
                        "output_dir": str(test_dir),
                        "metadata": {
                            "duree_estimee": result["timeline"].get("duree_totale", 0),
                            "nombre_parties": len(result["structure"].get("structure", [])),
                            "nombre_mots": result["scenario"].get("metadata", {}).get("nombre_mots", 0)
                        }
                    }
                    
                    console.print(f"✅ Test {test_num}/{total_tests} réussi: {model} - {ton}/{forme}")
                
                except Exception as e:
                    console.print(f"❌ Test {test_num}/{total_tests} échoué: {str(e)}")
                    test_result = {
                        "test_id": test_num,
                        "model": model,
                        "parameters": {
                            "ton": ton,
                            "forme": forme,
                            "public_cible": public,
                            "densite_narrative": densite,
                            "style_linguistique": style
                        },
                        "status": "error",
                        "error": str(e)
                    }
                
                results["tests"].append(test_result)
                progress.advance(task)
    
    # Sauvegarder les résultats globaux
    with open(output_dir / "gridsearch_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Afficher le résumé
    display_summary(results)
    
    return results


def display_summary(results: Dict[str, Any]):
    """Affiche un résumé des résultats."""
    
    successes = [t for t in results["tests"] if t["status"] == "success"]
    failures = [t for t in results["tests"] if t["status"] == "error"]
    
    console.print("\n" + "="*60)
    console.print(Panel(
        f"[bold green]Tests réussis : {len(successes)}/{results['total_tests']}[/bold green]\n"
        f"[bold red]Tests échoués : {len(failures)}/{results['total_tests']}[/bold red]\n\n"
        f"[cyan]Dossier de sortie : {results['run_id']}[/cyan]",
        title="📊 Résumé du Gridsearch",
        border_style="green"
    ))
    
    if successes:
        table = Table(title="✅ Tests Réussis", show_lines=True)
        table.add_column("Test", style="cyan", width=6)
        table.add_column("Modèle", style="yellow", width=15)
        table.add_column("Ton", style="green", width=20)
        table.add_column("Forme", style="blue", width=18)
        table.add_column("Durée", style="magenta", width=8)
        
        for test in successes[:10]:  # Afficher les 10 premiers
            table.add_row(
                str(test["test_id"]),
                test["model"],
                test["parameters"]["ton"],
                test["parameters"]["forme"],
                f"{test['metadata'].get('duree_estimee', 0):.0f}s"
            )
        
        console.print(table)
        
        if len(successes) > 10:
            console.print(f"\n[dim]... et {len(successes) - 10} autres tests réussis[/dim]")


def main():
    parser = argparse.ArgumentParser(description="Gridsearch Groq × Configuration JSON")
    parser.add_argument(
        "--mode",
        choices=["quick", "standard", "full"],
        default="standard",
        help="Mode de test : quick (4 tests), standard (12 tests), full (32 tests)"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(GROQ_MODELS.keys()),
        default=["llama-3.1-8b", "llama-3.1-70b"],
        help="Modèles Groq à tester"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="Créez un récit sonore sur la vie des ouvriers au début du 20ème siècle",
        help="Prompt de base pour tous les tests"
    )
    
    args = parser.parse_args()
    
    # Créer le dossier de sortie
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("output") / "gridsearch_groq" / f"run_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    console.print(Panel(
        "[bold cyan]🚀 Démarrage du Gridsearch Groq[/bold cyan]\n\n"
        "Ce script va tester différentes combinaisons de:\n"
        "• Modèles Groq (Llama, Mixtral, Gemma)\n"
        "• Paramètres JSON (ton, forme, public, densité, style)",
        title="Gridsearch Groq × JSON",
        border_style="cyan"
    ))
    
    # Lancer le gridsearch
    results = run_gridsearch(
        models=args.models,
        prompt=args.prompt,
        output_dir=output_dir,
        mode=args.mode
    )
    
    console.print(f"\n✅ [bold green]Gridsearch terminé ![/bold green]")
    console.print(f"📁 Résultats sauvegardés dans : {output_dir}")
    console.print(f"\n💡 Analysez les résultats avec:")
    console.print(f"   [cyan]python analyze_gridsearch.py --input {output_dir}[/cyan]")


if __name__ == "__main__":
    main()
