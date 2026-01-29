"""
Gridsearch pour tester l'influence des paramètres de CONFIGURATION JSON sur la génération.

Ce script teste différentes combinaisons de :
- Forme narrative (documentaire, interview, conte, etc.)
- Ton (neutre, émotionnel, dramatique, etc.)
- Axe narratif (chronologique, thématique, etc.)
- Durée
- Autres paramètres de configuration

Usage:
    # Mode standard (9 tests)
    python gridsearch_config.py
    
    # Avec prompt personnalisé
    python gridsearch_config.py "Votre prompt ici"
    
    # Mode complet (tous les paramètres)
    python gridsearch_config.py --full
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import itertools
import copy

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

# Paramètres LLM fixes (optimaux trouvés via gridsearch_local.py)
FIXED_LLM_PARAMS = {
    'temperature': 0.7,
    'max_tokens': 3072,
    'top_p': 0.9,
    'repeat_penalty': 1.05
}

# GRILLE DE CONFIGURATION STANDARD (9 tests)
CONFIG_GRID = {
    'forme': ['documentaire', 'reportage', 'témoignage'],
    'ton': ['neutre_informatif', 'emotionnel_personnel', 'dramatique_immersif'],
    'axe_narratif': ['mixte'],  # Fixé
    'duree': [180],  # 3 minutes (fixé pour comparaison)
}
# Total: 3 formes × 3 tons × 1 axe × 1 durée = 9 tests

# GRILLE COMPLÈTE (27 tests)
CONFIG_GRID_FULL = {
    'forme': ['documentaire', 'interview', 'reportage', 'témoignage'],
    'ton': ['neutre_informatif', 'emotionnel_personnel', 'dramatique_immersif'],
    'axe_narratif': ['chronologique', 'mixte', 'thematique'],
    'duree': [180],
}
# Total: 4 × 3 × 3 × 1 = 36 tests

# GRILLE RAPIDE (3 tests)
CONFIG_GRID_QUICK = {
    'forme': ['documentaire', 'témoignage'],
    'ton': ['neutre_informatif'],
    'axe_narratif': ['mixte'],
    'duree': [180],
}
# Total: 2 × 1 × 1 × 1 = 2 tests


def load_base_config() -> Dict:
    """Charge la configuration par défaut."""
    config_path = Path("config/default_config.json")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def create_modified_config(base_config: Dict, modifications: Dict) -> Dict:
    """Crée une config modifiée avec les paramètres du gridsearch."""
    config = copy.deepcopy(base_config)
    
    # Appliquer les modifications
    if 'forme' in modifications:
        config['generation_parameters']['forme']['value'] = modifications['forme']
        config['generation_parameters']['forme']['user_specified'] = True
    
    if 'ton' in modifications:
        config['generation_parameters']['ton']['value'] = modifications['ton']
        config['generation_parameters']['ton']['user_specified'] = True
    
    if 'axe_narratif' in modifications:
        config['generation_parameters']['axe_narratif']['value'] = modifications['axe_narratif']
        config['generation_parameters']['axe_narratif']['user_specified'] = True
    
    if 'duree' in modifications:
        config['generation_parameters']['duree']['value'] = modifications['duree']
        config['generation_parameters']['duree']['user_specified'] = True
    
    return config


def generate_config_combinations(config_grid: Dict[str, List]) -> List[Dict]:
    """Génère toutes les combinaisons de configurations."""
    keys = list(config_grid.keys())
    values = list(config_grid.values())
    
    combinations = []
    for combo in itertools.product(*values):
        combinations.append(dict(zip(keys, combo)))
    
    return combinations


def run_single_config_test(
    prompt: str,
    config_modifications: Dict[str, Any],
    test_id: int,
    total_tests: int,
    output_dir: Path
) -> Dict[str, Any]:
    """Lance un test avec une configuration modifiée."""
    from utils.ollama_client import OllamaClientWrapper
    from utils.skill_loader import SkillLoader
    
    logger.info(f"\n{'='*80}")
    logger.info(f"TEST {test_id}/{total_tests}")
    logger.info(f"{'='*80}")
    logger.info(f"Configuration testée:")
    for key, value in config_modifications.items():
        logger.info(f"  - {key}: {value}")
    logger.info(f"Prompt: {prompt}")
    
    # Créer client avec paramètres LLM optimaux
    ollama_client = OllamaClientWrapper(
        model=BASE_OLLAMA_CONFIG['model'],
        base_url=BASE_OLLAMA_CONFIG['base_url'],
        timeout=BASE_OLLAMA_CONFIG['timeout']
    )
    
    # Appliquer paramètres LLM fixes
    ollama_client.client.default_temperature = FIXED_LLM_PARAMS['temperature']
    ollama_client.client.default_max_tokens = FIXED_LLM_PARAMS['max_tokens']
    ollama_client.client.default_top_p = FIXED_LLM_PARAMS['top_p']
    ollama_client.client.default_repeat_penalty = FIXED_LLM_PARAMS['repeat_penalty']
    
    # Load base config et appliquer modifications
    base_config = load_base_config()
    modified_config = create_modified_config(base_config, config_modifications)
    
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
        'config_modifications': config_modifications,
        'llm_params': FIXED_LLM_PARAMS,
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
        config = agent_0.parse(prompt, "simple", modified_config)
        results['outputs']['config'] = config
        
        # Agent 1: Create structure
        logger.info("Agent 1: Creating narrative structure...")
        agent_1 = agents['agent_1_structure']['instance']
        structure = agent_1.create_narrative_structure(config, 1)
        results['outputs']['structure'] = structure
        results['metrics']['num_parts'] = len(structure.get('structure', []))
        
        # Agent 2: Write scenario
        logger.info("Agent 2: Writing scenario...")
        agent_2 = agents['agent_2_writing']['instance']
        agent_2.set_skills(skills)
        scenario = agent_2.write_complete_scenario(structure, config)
        results['outputs']['scenario'] = scenario
        results['metrics']['word_count'] = scenario.get('metadata', {}).get('nombre_mots', 0)
        results['metrics']['estimated_duration'] = scenario.get('duree_estimee', 0)
        
        # Agent 3: Create timeline
        logger.info("Agent 3: Creating audio timeline...")
        agent_3 = agents['agent_3_production']['instance']
        agent_3.set_skills(skills)
        timeline = agent_3.create_audio_timeline(scenario, None, config)
        results['outputs']['timeline'] = timeline
        
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
        'config_modifications': results['config_modifications'],
        'llm_params': results['llm_params'],
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
            'config_modifications': result['config_modifications'],
            'success': result['success'],
            'metrics': result['metrics']
        }
        report['tests'].append(test_summary)
    
    # Sauvegarder rapport JSON
    report_file = output_dir / "comparison_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Générer rapport texte
    report_txt = output_dir / "comparison_report.txt"
    with open(report_txt, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("RAPPORT DE GRIDSEARCH - Paramètres de Configuration\n")
        f.write("="*80 + "\n\n")
        
        f.write(f"Total de tests: {report['total_tests']}\n")
        f.write(f"Réussis: {report['successful_tests']}\n")
        f.write(f"Échoués: {report['failed_tests']}\n\n")
        
        f.write("-"*80 + "\n")
        f.write("RÉSULTATS PAR TEST\n")
        f.write("-"*80 + "\n\n")
        
        for test in report['tests']:
            f.write(f"Test {test['test_id']}: {'✓ SUCCÈS' if test['success'] else '✗ ÉCHEC'}\n")
            f.write(f"  Configuration:\n")
            for param, value in test['config_modifications'].items():
                f.write(f"    - {param}: {value}\n")
            
            if test['success'] and test.get('metrics'):
                f.write(f"  Métriques:\n")
                f.write(f"    - Nombre de mots: {test['metrics'].get('word_count', 'N/A')}\n")
                f.write(f"    - Nombre de parties: {test['metrics'].get('num_parts', 'N/A')}\n")
                f.write(f"    - Durée estimée: {test['metrics'].get('estimated_duration', 'N/A'):.1f}s\n")
            
            f.write("\n")
        
        # Analyse par paramètre
        f.write("-"*80 + "\n")
        f.write("ANALYSE PAR PARAMÈTRE\n")
        f.write("-"*80 + "\n\n")
        
        analysis = analyze_config_impact(report['tests'])
        for param, stats in analysis.items():
            f.write(f"{param.upper()}:\n")
            for value, metrics in stats.items():
                f.write(f"  {value}:\n")
                f.write(f"    - Tests réussis: {metrics['success_count']}/{metrics['total_count']}\n")
                if metrics['avg_words'] > 0:
                    f.write(f"    - Moyenne mots: {metrics['avg_words']:.0f}\n")
                    f.write(f"    - Moyenne parties: {metrics['avg_parts']:.1f}\n")
            f.write("\n")
    
    logger.info(f"Rapport sauvegardé: {report_file}")
    logger.info(f"Rapport texte: {report_txt}")
    
    return report


def analyze_config_impact(tests: List[Dict]) -> Dict:
    """Analyse l'impact de chaque paramètre de configuration."""
    from collections import defaultdict
    
    param_stats = defaultdict(lambda: defaultdict(lambda: {
        'total_count': 0,
        'success_count': 0,
        'total_words': 0,
        'total_parts': 0
    }))
    
    for test in tests:
        for param, value in test['config_modifications'].items():
            stats = param_stats[param][value]
            stats['total_count'] += 1
            
            if test['success']:
                stats['success_count'] += 1
                if 'metrics' in test and test['metrics']:
                    stats['total_words'] += test['metrics'].get('word_count', 0)
                    stats['total_parts'] += test['metrics'].get('num_parts', 0)
    
    # Calculer moyennes
    analysis = {}
    for param, values in param_stats.items():
        analysis[param] = {}
        for value, stats in values.items():
            success_count = stats['success_count']
            analysis[param][value] = {
                'total_count': stats['total_count'],
                'success_count': success_count,
                'avg_words': stats['total_words'] / success_count if success_count > 0 else 0,
                'avg_parts': stats['total_parts'] / success_count if success_count > 0 else 0
            }
    
    return analysis


def main():
    """Main function pour gridsearch de configuration."""
    print("\n" + "="*80)
    print("🔬 GRIDSEARCH - Test des Paramètres de Configuration JSON")
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
        config_grid = CONFIG_GRID_QUICK
        mode_name = "RAPIDE"
    elif full_mode:
        config_grid = CONFIG_GRID_FULL
        mode_name = "COMPLET"
    else:
        config_grid = CONFIG_GRID
        mode_name = "STANDARD"
    
    # Générer combinaisons
    combinations = generate_config_combinations(config_grid)
    total_tests = len(combinations)
    
    print(f"\nMode: {mode_name}")
    print(f"Nombre de combinaisons à tester: {total_tests}")
    print(f"Prompt: {prompt}")
    
    # Estimer durée
    if total_tests <= 5:
        duree_estimee = "~30-45 minutes"
    elif total_tests <= 12:
        duree_estimee = "~1-2 heures"
    elif total_tests <= 30:
        duree_estimee = "~3-5 heures"
    else:
        duree_estimee = "~5-10 heures"
    
    print(f"Durée estimée: {duree_estimee}")
    print(f"\nParamètres LLM fixes (optimaux): {FIXED_LLM_PARAMS}\n")
    
    print("Paramètres de configuration testés:")
    for param, values in config_grid.items():
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
    output_dir = Path("output/gridsearch_config") / f"run_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Sauvegarder configuration du gridsearch
    config_file = output_dir / "gridsearch_config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump({
            'prompt': prompt,
            'mode': mode_name,
            'config_grid': config_grid,
            'llm_params_fixed': FIXED_LLM_PARAMS,
            'total_combinations': total_tests,
            'estimated_duration': duree_estimee,
            'timestamp': timestamp,
            'model': BASE_OLLAMA_CONFIG['model']
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nRésultats seront sauvegardés dans: {output_dir}\n")
    
    # Lancer tests
    all_results = []
    
    for i, config_mods in enumerate(combinations, 1):
        try:
            result = run_single_config_test(prompt, config_mods, i, total_tests, output_dir)
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
        print(f"  - test_XXX/scenario.json : Histoires générées")
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
