"""
Gridsearch pour tester l'influence des paramètres narratifs sur la génération.

Tests les variations de :
- Ton de l'histoire (dramatique, neutre, intimiste...)
- Forme (documentaire, conte, podcast...)
- Structure narrative (chronologique, flashback, thématique...)
- Époque linguistique (authentique, moderne...)
- Niveau de détail historique
- Perspective narrative (1ère/3ème personne...)
- Rythme

Usage:
    # Mode STANDARD (12 tests, ~1-2h) - Recommandé
    python gridsearch_local.py
    
    # Avec prompt personnalisé
    python gridsearch_local.py "Votre prompt ici"
    
    # Mode RAPIDE (2 tests, ~15-30min) - Debug
    python gridsearch_local.py --quick
    
    # Mode COMPLET (48 tests, ~6-10h) - Validation finale
    python gridsearch_local.py --full
"""

import os
import sys
import json
import logging
import random
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

# Grille STANDARD - Tests variés sur paramètres narratifs
PARAM_GRID = {
    'ton': ["neutre_informatif", "dramatique_immersif", "intimiste_confidentiel"],
    'forme': ["documentaire", "conte", "podcast_narratif"],
    'structure_narrative': ["chronologique", "flashback"],
    'epoque_linguistique': ["authentique"],
    'niveau_detail_historique': ["moyen"],
    'perspective_narrative': ["troisieme_personne"],
    'rythme': ["modere"]
}
# Total: 3 × 3 × 2 = 18 tests

# Grille COMPLÈTE (plus exhaustive, pour validation finale)
# Note: Génère un échantillon stratifié de max 50 combinaisons
PARAM_GRID_FULL = {
    'ton': ["neutre_informatif", "dramatique_immersif", "intimiste_confidentiel", "poetique_contemplatif"],
    'forme': ["documentaire", "conte", "podcast_narratif", "temoignage"],
    'structure_narrative': ["chronologique", "flashback", "thematique", "crescendo_emotionnel"],
    'epoque_linguistique': ["authentique", "modernise_accessible", "mixte"],
    'niveau_detail_historique': ["leger", "moyen", "approfondi"],
    'perspective_narrative': ["premiere_personne", "troisieme_personne"],
    'rythme': ["lent_contemplatif", "modere", "dynamique"]
}
# Total théorique: 4 × 4 × 4 × 3 × 3 × 2 × 3 = 2,304 tests
# Échantillonnage: ~50 tests représentatifs seront générés automatiquement

# Grille RAPIDE (test minimal, debug)
PARAM_GRID_QUICK = {
    'ton': ["neutre_informatif", "dramatique_immersif"],
    'forme': ["documentaire"],
    'structure_narrative': ["chronologique"],
    'epoque_linguistique': ["authentique"],
    'niveau_detail_historique': ["moyen"],
    'perspective_narrative': ["troisieme_personne"],
    'rythme': ["modere"]
}
# Total: 2 × 1 × 1 × 1 × 1 × 1 × 1 = 2 tests


def generate_param_combinations(param_grid: Dict[str, List], max_combinations: int = 50) -> List[Dict]:
    """
    Génère des combinaisons de paramètres.
    
    Pour le mode FULL, limite intelligemment le nombre de combinaisons en
    sélectionnant un échantillon représentatif plutôt que toutes les combinaisons.
    """
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    
    # Calculer le nombre total de combinaisons possibles
    total_possible = 1
    for v in values:
        total_possible *= len(v)
    
    # Si le nombre est raisonnable, générer toutes les combinaisons
    if total_possible <= max_combinations:
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
        return combinations
    
    # Sinon, générer un échantillon stratifié
    logger.info(f"Trop de combinaisons possibles ({total_possible}). Génération d'un échantillon de {max_combinations}.")
    
    # Stratégie : tester toutes les valeurs de chaque paramètre au moins une fois
    combinations = []
    random.seed(42)  # Reproductibilité
    
    # Générer des combinaisons aléatoires
    seen = set()
    attempts = 0
    max_attempts = max_combinations * 10
    
    while len(combinations) < max_combinations and attempts < max_attempts:
        combo_values = [random.choice(v) for v in values]
        combo_tuple = tuple(combo_values)
        
        if combo_tuple not in seen:
            seen.add(combo_tuple)
            combinations.append(dict(zip(keys, combo_values)))
        
        attempts += 1
    
    return combinations


def run_single_test(
    prompt: str,
    params: Dict[str, Any],
    test_id: int,
    total_tests: int,
    output_dir: Path
) -> Dict[str, Any]:
    """Lance un test avec une configuration narrative spécifique."""
    from utils.ollama_client import OllamaClientWrapper
    from utils.skill_loader import SkillLoader
    
    logger.info(f"\n{'='*80}")
    logger.info(f"TEST {test_id}/{total_tests}")
    logger.info(f"{'='*80}")
    logger.info(f"Paramètres narratifs: {params}")
    logger.info(f"Prompt: {prompt}")
    
    # Créer client Ollama avec config par défaut
    ollama_client = OllamaClientWrapper(
        model=BASE_OLLAMA_CONFIG['model'],
        base_url=BASE_OLLAMA_CONFIG['base_url'],
        timeout=BASE_OLLAMA_CONFIG['timeout']
    )
    
    # Load config par défaut
    config_path = Path("config/default_config.json")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            default_config = json.load(f)
    else:
        default_config = {}
    
    # Appliquer les paramètres narratifs à la config
    if 'scenario_config' in default_config and 'generation_parameters' in default_config['scenario_config']:
        gen_params = default_config['scenario_config']['generation_parameters']
        
        # Modifier les paramètres selon la grille de test
        for param_name, param_value in params.items():
            if param_name in gen_params:
                gen_params[param_name]['value'] = param_value
                gen_params[param_name]['user_specified'] = True
                logger.info(f"  → {param_name}: {param_value}")
    
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
        # Agent 0: Parse request (avec config modifiée)
        logger.info("Agent 0: Parsing request avec paramètres narratifs custom...")
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
    
    # Créer un nom descriptif pour le test
    test_name_parts = [f"test_{test_id:03d}"]
    
    # Ajouter les paramètres les plus importants au nom
    if 'ton' in params:
        test_name_parts.append(params['ton'])
    if 'forme' in params:
        test_name_parts.append(params['forme'])
    if 'structure_narrative' in params:
        test_name_parts.append(params['structure_narrative'])
    
    test_name = "_".join(test_name_parts)
    
    # Sauvegarder résultats individuels
    test_dir = output_dir / test_name
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
        f.write("RAPPORT DE GRIDSEARCH - Paramètres Narratifs\n")
        f.write("="*80 + "\n")
        f.write("Analyse de l'impact des paramètres narratifs sur la génération\n")
        f.write("(ton, forme, structure, époque linguistique, détail, perspective, rythme)\n")
        f.write("="*80 + "\n\n")
        
        f.write(f"Total de tests: {report['total_tests']}\n")
        f.write(f"Réussis: {report['successful_tests']}\n")
        f.write(f"Échoués: {report['failed_tests']}\n\n")
        
        f.write("-"*80 + "\n")
        f.write("RÉSULTATS PAR TEST\n")
        f.write("-"*80 + "\n\n")
        
        for test in report['tests']:
            f.write(f"Test {test['test_id']}: {'✓ SUCCÈS' if test['success'] else '✗ ÉCHEC'}\n")
            f.write(f"  Paramètres narratifs:\n")
            for param, value in test['params'].items():
                f.write(f"    - {param}: {value}\n")
            
            if test['success'] and 'quality' in test:
                f.write(f"  Qualité:\n")
                f.write(f"    - Nombre de mots: {test['quality']['word_count']}\n")
                f.write(f"    - Nombre de parties: {test['quality']['num_parts']}\n")
                f.write(f"    - Durée estimée: {test['quality']['estimated_duration']:.1f}s\n")
            
            if 'metrics' in test:
                f.write(f"  Métriques de génération:\n")
                for metric_name, metric_value in test['metrics'].items():
                    if metric_value and 'duration' in metric_name:
                        f.write(f"    - {metric_name}: {metric_value:.2f}s\n")
            
            f.write("\n")
        
        f.write("-"*80 + "\n")
        f.write("ANALYSE DE L'IMPACT DES PARAMÈTRES NARRATIFS\n")
        f.write("-"*80 + "\n\n")
        
        # Analyser l'impact de chaque paramètre
        param_analysis = analyze_parameter_impact(report['tests'])
        for param, analysis in param_analysis.items():
            f.write(f"\n{param.upper().replace('_', ' ')}:\n")
            f.write("-" * 40 + "\n")
            for value, stats in analysis.items():
                f.write(f"  • {value}:\n")
                f.write(f"      Succès: {stats['success_rate']:.1%}\n")
                f.write(f"      Mots moyen: {stats['avg_words']:.0f}\n")
                if stats.get('avg_duration'):
                    f.write(f"      Durée moyenne: {stats['avg_duration']:.1f}s\n")
            f.write("\n")
    
    logger.info(f"Rapport sauvegardé: {report_file}")
    logger.info(f"Rapport texte: {report_txt}")
    
    return report


def analyze_parameter_impact(tests: List[Dict]) -> Dict:
    """Analyse l'impact de chaque paramètre narratif."""
    from collections import defaultdict
    
    param_stats = defaultdict(lambda: defaultdict(lambda: {
        'count': 0,
        'success': 0,
        'total_words': 0,
        'total_duration': 0
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
                stats['total_duration'] += test['quality'].get('estimated_duration', 0)
    
    # Calculer moyennes
    analysis = {}
    for param, values in param_stats.items():
        analysis[param] = {}
        for value, stats in values.items():
            if stats['count'] > 0:
                analysis[param][value] = {
                    'success_rate': stats['success'] / stats['count'],
                    'avg_words': stats['total_words'] / stats['count'],
                    'avg_duration': stats['total_duration'] / stats['count'] if stats['total_duration'] > 0 else None
                }
    
    return analysis


def main():
    """Main function pour gridsearch."""
    print("\n" + "="*80)
    print("🔬 GRIDSEARCH - Test des Paramètres Narratifs")
    print("="*80)
    print("\nTestera les variations de:")
    print("  • Ton de l'histoire")
    print("  • Forme (documentaire, conte, podcast...)")
    print("  • Structure narrative")
    print("  • Époque linguistique")
    print("  • Niveau de détail historique")
    print("  • Perspective narrative")
    print("  • Rythme")
    print()
    
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
    if full_mode:
        combinations = generate_param_combinations(param_grid, max_combinations=50)
    else:
        combinations = generate_param_combinations(param_grid, max_combinations=100)
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
    
    # Afficher les paramètres narratifs testés
    print("Paramètres narratifs testés:")
    for param, values in param_grid.items():
        param_display = param.replace('_', ' ').title()
        if len(values) > 3:
            values_display = f"{values[:3]}... ({len(values)} valeurs)"
        else:
            values_display = values
        print(f"  • {param_display}: {values_display}")
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
            'type': 'narrative_parameters_gridsearch',
            'description': 'Tests de variations de paramètres narratifs (ton, forme, structure, etc.)',
            'prompt': prompt,
            'mode': mode_name,
            'param_grid': param_grid,
            'total_combinations': total_tests,
            'estimated_duration': duree_estimee,
            'timestamp': timestamp,
            'model': BASE_OLLAMA_CONFIG['model'],
            'parameters_tested': list(param_grid.keys())
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
