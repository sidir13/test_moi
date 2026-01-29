"""
Gridsearch pour tester l'influence des paramètres LLM sur la génération.

Usage:
    # Mode STANDARD (12 tests, ~1-2h) - Recommandé
    python gridsearch_local.py
    
    # Avec prompt personnalisé
    python gridsearch_local.py "Votre prompt ici"
    
    # Mode RAPIDE (2 tests, ~15-30min) - Debug
    python gridsearch_local.py --quick
    
    # Mode COMPLET (32 tests, ~4-8h) - Validation finale
    python gridsearch_local.py --full
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import itertools

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration de base
BASE_OLLAMA_CONFIG = {
    'model': 'qwen3:8b',
    'base_url': 'http://localhost:11434',
    'timeout': 600
}

# Grille STANDARD (~10 tests) - Recommandée pour exploration locale
PARAM_GRID = {
    'temperature': [0.3, 0.5, 0.7, 0.9],      # 4 valeurs
    'max_tokens': [3072],                      # 1 valeur (fixe)
    'top_p': [0.9],                            # 1 valeur (fixe)
    'repeat_penalty': [1.0, 1.05, 1.1],       # 3 valeurs
}
# Total: 4 × 1 × 1 × 3 = 12 tests

# Grille COMPLÈTE (plus exhaustive, pour validation finale)
PARAM_GRID_FULL = {
    'temperature': [0.3, 0.5, 0.7, 0.9],
    'max_tokens': [2048, 4096],
    'top_p': [0.9, 0.95],
    'repeat_penalty': [1.0, 1.1],
}
# Total: 4 × 2 × 2 × 2 = 32 tests

# Grille RAPIDE (test minimal, debug)
PARAM_GRID_QUICK = {
    'temperature': [0.3, 0.7],
    'max_tokens': [3072],
    'top_p': [0.9],
    'repeat_penalty': [1.0],
}
# Total: 2 × 1 × 1 × 1 = 2 tests


def generate_param_combinations(param_grid: Dict[str, List]) -> List[Dict]:
    """Génère toutes les combinaisons de paramètres."""
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    
    combinations = []
    for combo in itertools.product(*values):
        combinations.append(dict(zip(keys, combo)))
    
    return combinations


def run_single_test(
    prompt: str,
    params: Dict[str, Any],
    test_id: int,
    total_tests: int,
    output_dir: Path
) -> Dict[str, Any]:
    """Lance un test avec une configuration de paramètres."""
    from utils.ollama_client import OllamaClientWrapper
    from utils.skill_loader import SkillLoader
    
    logger.info(f"\n{'='*80}")
    logger.info(f"TEST {test_id}/{total_tests}")
    logger.info(f"{'='*80}")
    logger.info(f"Paramètres: {params}")
    logger.info(f"Prompt: {prompt}")
    
    # Créer client avec paramètres custom
    ollama_client = OllamaClientWrapper(
        model=BASE_OLLAMA_CONFIG['model'],
        base_url=BASE_OLLAMA_CONFIG['base_url'],
        timeout=BASE_OLLAMA_CONFIG['timeout']
    )
    
    # Modifier les paramètres du client
    ollama_client.client.default_temperature = params.get('temperature', 0.7)
    ollama_client.client.default_max_tokens = params.get('max_tokens', 4096)
    ollama_client.client.default_top_p = params.get('top_p', 0.9)
    ollama_client.client.default_repeat_penalty = params.get('repeat_penalty', 1.0)
    
    # Load config
    config_path = Path("config/default_config.json")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            default_config = json.load(f)
    else:
        default_config = {}
    
    # Load agents
    agents_dir = Path("agents")
    agents = SkillLoader.load_all_skills(
        agents_dir,
        ollama_client.client,
        skill_type="agents"
    )
    
    # Load skills
    skills_dir = Path("skills")
    skills = SkillLoader.load_all_skills(
        skills_dir,
        ollama_client.client,
        skill_type="skills"
    )
    
    results = {
        'test_id': test_id,
        'params': params,
        'prompt': prompt,
        'timestamp': datetime.now().isoformat(),
        'success': False,
        'outputs': {},
        'metrics': {},
        'errors': []
    }
    
    try:
        # Agent 0: Parse request
        logger.info("Agent 0: Parsing request...")
        agent_0 = agents['agent_0_request_parser']['instance']
        config = agent_0.parse(prompt, "simple", default_config)
        results['outputs']['config'] = config
        results['metrics']['config_duration'] = agent_0.last_duration if hasattr(agent_0, 'last_duration') else None
        
        # Agent 1: Create structure
        logger.info("Agent 1: Creating narrative structure...")
        agent_1 = agents['agent_1_structure']['instance']
        structure = agent_1.create_narrative_structure(config, 1)
        results['outputs']['structure'] = structure
        results['metrics']['structure_duration'] = agent_1.last_duration if hasattr(agent_1, 'last_duration') else None
        
        # Agent 2: Write scenario
        logger.info("Agent 2: Writing scenario...")
        agent_2 = agents['agent_2_writing']['instance']
        agent_2.set_skills(skills)
        scenario = agent_2.write_complete_scenario(structure, config)
        results['outputs']['scenario'] = scenario
        results['metrics']['scenario_duration'] = agent_2.last_duration if hasattr(agent_2, 'last_duration') else None
        results['metrics']['word_count'] = scenario.get('metadata', {}).get('nombre_mots', 0)
        
        # Agent 3: Create timeline
        logger.info("Agent 3: Creating audio timeline...")
        agent_3 = agents['agent_3_production']['instance']
        agent_3.set_skills(skills)
        timeline = agent_3.create_audio_timeline(scenario, None, config)
        results['outputs']['timeline'] = timeline
        results['metrics']['timeline_duration'] = agent_3.last_duration if hasattr(agent_3, 'last_duration') else None
        
        results['success'] = True
        logger.info(f"✓ Test {test_id} réussi")
        
    except Exception as e:
        logger.error(f"✗ Test {test_id} échoué: {e}")
        results['errors'].append(str(e))
        results['success'] = False
    
    # Sauvegarder résultats individuels
    test_dir = output_dir / f"test_{test_id:03d}"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Sauvegarder chaque output
    for output_name, output_data in results['outputs'].items():
        output_file = test_dir / f"{output_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    # Sauvegarder métadonnées du test
    metadata_file = test_dir / "metadata.json"
    metadata = {
        'test_id': results['test_id'],
        'params': results['params'],
        'prompt': results['prompt'],
        'timestamp': results['timestamp'],
        'success': results['success'],
        'metrics': results['metrics'],
        'errors': results['errors']
    }
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Résultats sauvegardés dans: {test_dir}")
    
    return results


def generate_comparison_report(all_results: List[Dict], output_dir: Path):
    """Génère un rapport comparatif des résultats."""
    logger.info("\n" + "="*80)
    logger.info("GÉNÉRATION DU RAPPORT COMPARATIF")
    logger.info("="*80)
    
    report = {
        'total_tests': len(all_results),
        'successful_tests': sum(1 for r in all_results if r['success']),
        'failed_tests': sum(1 for r in all_results if not r['success']),
        'tests': []
    }
    
    for result in all_results:
        test_summary = {
            'test_id': result['test_id'],
            'params': result['params'],
            'success': result['success'],
            'metrics': result['metrics']
        }
        
        # Ajouter des métriques de qualité si disponibles
        if result['success'] and 'scenario' in result['outputs']:
            scenario = result['outputs']['scenario']
            test_summary['quality'] = {
                'word_count': scenario.get('metadata', {}).get('nombre_mots', 0),
                'num_parts': len(scenario.get('parties', [])),
                'estimated_duration': scenario.get('duree_estimee', 0)
            }
        
        report['tests'].append(test_summary)
    
    # Sauvegarder rapport
    report_file = output_dir / "comparison_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Générer rapport texte
    report_txt = output_dir / "comparison_report.txt"
    with open(report_txt, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("RAPPORT DE GRIDSEARCH - Paramètres LLM\n")
        f.write("="*80 + "\n\n")
        
        f.write(f"Total de tests: {report['total_tests']}\n")
        f.write(f"Réussis: {report['successful_tests']}\n")
        f.write(f"Échoués: {report['failed_tests']}\n\n")
        
        f.write("-"*80 + "\n")
        f.write("RÉSULTATS PAR TEST\n")
        f.write("-"*80 + "\n\n")
        
        for test in report['tests']:
            f.write(f"Test {test['test_id']}: {'✓ SUCCÈS' if test['success'] else '✗ ÉCHEC'}\n")
            f.write(f"  Paramètres:\n")
            for param, value in test['params'].items():
                f.write(f"    - {param}: {value}\n")
            
            if test['success'] and 'quality' in test:
                f.write(f"  Qualité:\n")
                f.write(f"    - Nombre de mots: {test['quality']['word_count']}\n")
                f.write(f"    - Nombre de parties: {test['quality']['num_parts']}\n")
                f.write(f"    - Durée estimée: {test['quality']['estimated_duration']:.1f}s\n")
            
            f.write("\n")
        
        f.write("-"*80 + "\n")
        f.write("ANALYSE DES PARAMÈTRES\n")
        f.write("-"*80 + "\n\n")
        
        # Analyser l'impact de chaque paramètre
        param_analysis = analyze_parameter_impact(report['tests'])
        for param, analysis in param_analysis.items():
            f.write(f"{param.upper()}:\n")
            for value, stats in analysis.items():
                f.write(f"  {value}: {stats['success_rate']:.1%} succès, ")
                f.write(f"avg {stats['avg_words']:.0f} mots\n")
            f.write("\n")
    
    logger.info(f"Rapport sauvegardé: {report_file}")
    logger.info(f"Rapport texte: {report_txt}")
    
    return report


def analyze_parameter_impact(tests: List[Dict]) -> Dict:
    """Analyse l'impact de chaque paramètre."""
    from collections import defaultdict
    
    param_stats = defaultdict(lambda: defaultdict(lambda: {
        'count': 0,
        'success': 0,
        'total_words': 0
    }))
    
    for test in tests:
        if not test['success']:
            continue
        
        for param, value in test['params'].items():
            stats = param_stats[param][value]
            stats['count'] += 1
            stats['success'] += 1 if test['success'] else 0
            
            if 'quality' in test:
                stats['total_words'] += test['quality']['word_count']
    
    # Calculer moyennes
    analysis = {}
    for param, values in param_stats.items():
        analysis[param] = {}
        for value, stats in values.items():
            if stats['count'] > 0:
                analysis[param][value] = {
                    'success_rate': stats['success'] / stats['count'],
                    'avg_words': stats['total_words'] / stats['count']
                }
    
    return analysis


def main():
    """Main function pour gridsearch."""
    print("\n" + "="*80)
    print("🔬 GRIDSEARCH - Test des Paramètres LLM")
    print("="*80)
    
    # Parse arguments
    quick_mode = '--quick' in sys.argv
    full_mode = '--full' in sys.argv
    args = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    
    # Prompt
    if args:
        prompt = " ".join(args)
    else:
        prompt = "Un documentaire de 3 minutes sur une grève de dockers en 1905"
        print(f"\nUtilisation du prompt par défaut: {prompt}")
    
    # Choisir la grille
    if quick_mode:
        param_grid = PARAM_GRID_QUICK
        mode_name = "RAPIDE"
    elif full_mode:
        param_grid = PARAM_GRID_FULL
        mode_name = "COMPLET"
    else:
        param_grid = PARAM_GRID  # Standard par défaut
        mode_name = "STANDARD"
    
    # Générer combinaisons
    combinations = generate_param_combinations(param_grid)
    total_tests = len(combinations)
    
    print(f"\nMode: {mode_name}")
    print(f"Nombre de combinaisons à tester: {total_tests}")
    print(f"Prompt: {prompt}")
    
    # Estimer durée
    if total_tests <= 5:
        duree_estimee = "~15-30 minutes"
    elif total_tests <= 12:
        duree_estimee = "~1-2 heures"
    elif total_tests <= 20:
        duree_estimee = "~2-4 heures"
    else:
        duree_estimee = "~4-8 heures"
    
    print(f"Durée estimée: {duree_estimee}\n")
    
    # Afficher les paramètres testés
    print("Paramètres testés:")
    for param, values in param_grid.items():
        print(f"  - {param}: {values}")
    print()
    
    # Confirmer
    if total_tests > 15:
        print(f"⚠️  {total_tests} tests vont être lancés.")
        print(f"Cela va prendre {duree_estimee}.")
        response = input("Continuer? (o/N) ")
        if response.lower() not in ['o', 'oui', 'y', 'yes']:
            print("Annulé.")
            return
    
    # Créer dossier de sortie
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("output/gridsearch") / f"run_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Sauvegarder configuration du gridsearch
    config_file = output_dir / "gridsearch_config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump({
            'prompt': prompt,
            'mode': mode_name,
            'param_grid': param_grid,
            'total_combinations': total_tests,
            'estimated_duration': duree_estimee,
            'timestamp': timestamp,
            'model': BASE_OLLAMA_CONFIG['model']
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nRésultats seront sauvegardés dans: {output_dir}\n")
    
    # Lancer tests
    all_results = []
    
    for i, params in enumerate(combinations, 1):
        try:
            result = run_single_test(prompt, params, i, total_tests, output_dir)
            all_results.append(result)
            
            # Afficher progression
            success_rate = sum(1 for r in all_results if r['success']) / len(all_results)
            print(f"\nProgression: {i}/{total_tests} ({i/total_tests:.1%})")
            print(f"Taux de succès: {success_rate:.1%}\n")
            
        except KeyboardInterrupt:
            logger.warning("\n⚠️  Interruption par l'utilisateur")
            break
        except Exception as e:
            logger.error(f"Erreur fatale test {i}: {e}")
            continue
    
    # Générer rapport final
    if all_results:
        report = generate_comparison_report(all_results, output_dir)
        
        print("\n" + "="*80)
        print("✅ GRIDSEARCH TERMINÉ")
        print("="*80)
        print(f"\nTests réussis: {report['successful_tests']}/{report['total_tests']}")
        print(f"Résultats dans: {output_dir}")
        print(f"\nConsultez:")
        print(f"  - comparison_report.txt : Rapport détaillé")
        print(f"  - comparison_report.json : Données brutes")
        print(f"  - test_XXX/ : Résultats individuels")
        print("\n" + "="*80)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Interruption par l'utilisateur")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ Erreur fatale: {e}", exc_info=True)
        sys.exit(1)
