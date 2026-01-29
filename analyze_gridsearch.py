"""
Analyse et visualise les résultats du gridsearch.

Usage:
    python analyze_gridsearch.py output/gridsearch/run_YYYYMMDD_HHMMSS
"""

import sys
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

def load_gridsearch_results(run_dir: Path) -> Dict:
    """Charge les résultats d'un run de gridsearch."""
    report_file = run_dir / "comparison_report.json"
    
    if not report_file.exists():
        print(f"Erreur: Rapport non trouvé dans {run_dir}")
        return None
    
    with open(report_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_summary(report: Dict):
    """Affiche un résumé des résultats."""
    print("\n" + "="*80)
    print("RÉSUMÉ DU GRIDSEARCH")
    print("="*80)
    print(f"Total de tests: {report['total_tests']}")
    print(f"Réussis: {report['successful_tests']} ({report['successful_tests']/report['total_tests']:.1%})")
    print(f"Échoués: {report['failed_tests']} ({report['failed_tests']/report['total_tests']:.1%})")


def analyze_by_parameter(report: Dict):
    """Analyse l'impact de chaque paramètre."""
    print("\n" + "="*80)
    print("ANALYSE PAR PARAMÈTRE")
    print("="*80)
    
    # Collecter stats par paramètre
    param_stats = defaultdict(lambda: defaultdict(lambda: {
        'count': 0,
        'success': 0,
        'total_words': 0,
        'total_duration': 0
    }))
    
    for test in report['tests']:
        if not test['success']:
            continue
        
        for param, value in test['params'].items():
            stats = param_stats[param][value]
            stats['count'] += 1
            stats['success'] += 1
            
            if 'quality' in test:
                stats['total_words'] += test['quality']['word_count']
                stats['total_duration'] += test['quality']['estimated_duration']
    
    # Afficher stats
    for param, values in sorted(param_stats.items()):
        print(f"\n{param.upper()}:")
        print("-" * 60)
        
        for value in sorted(values.keys()):
            stats = values[value]
            if stats['count'] > 0:
                avg_words = stats['total_words'] / stats['count']
                avg_duration = stats['total_duration'] / stats['count']
                success_rate = stats['success'] / stats['count']
                
                print(f"  {value:>10} : {stats['count']:>2} tests, "
                      f"{success_rate:>5.1%} succès, "
                      f"{avg_words:>6.0f} mots, "
                      f"{avg_duration:>5.1f}s durée")


def find_best_config(report: Dict):
    """Trouve la meilleure configuration."""
    print("\n" + "="*80)
    print("MEILLEURES CONFIGURATIONS")
    print("="*80)
    
    successful_tests = [t for t in report['tests'] if t['success']]
    
    if not successful_tests:
        print("Aucun test réussi.")
        return
    
    # Meilleure pour nombre de mots
    best_words = max(successful_tests, key=lambda t: t.get('quality', {}).get('word_count', 0))
    print("\nPlus de mots générés:")
    print(f"  Test {best_words['test_id']}")
    print(f"  Paramètres: {best_words['params']}")
    print(f"  Mots: {best_words['quality']['word_count']}")
    
    # Meilleure pour durée
    best_duration = max(successful_tests, key=lambda t: t.get('quality', {}).get('estimated_duration', 0))
    print("\nDurée la plus longue:")
    print(f"  Test {best_duration['test_id']}")
    print(f"  Paramètres: {best_duration['params']}")
    print(f"  Durée: {best_duration['quality']['estimated_duration']:.1f}s")
    
    # Configuration "équilibrée" (mots * durée)
    balanced = max(successful_tests, 
                   key=lambda t: t.get('quality', {}).get('word_count', 0) * 
                                 t.get('quality', {}).get('estimated_duration', 0))
    print("\nConfiguration équilibrée (mots × durée):")
    print(f"  Test {balanced['test_id']}")
    print(f"  Paramètres: {balanced['params']}")
    print(f"  Mots: {balanced['quality']['word_count']}")
    print(f"  Durée: {balanced['quality']['estimated_duration']:.1f}s")


def compare_temperatures(report: Dict):
    """Compare spécifiquement l'impact de la température."""
    print("\n" + "="*80)
    print("FOCUS: IMPACT DE LA TEMPÉRATURE")
    print("="*80)
    
    temp_groups = defaultdict(list)
    
    for test in report['tests']:
        if not test['success']:
            continue
        temp = test['params']['temperature']
        temp_groups[temp].append(test)
    
    print("\nStatistiques par température:")
    print("-" * 60)
    
    for temp in sorted(temp_groups.keys()):
        tests = temp_groups[temp]
        avg_words = sum(t['quality']['word_count'] for t in tests) / len(tests)
        min_words = min(t['quality']['word_count'] for t in tests)
        max_words = max(t['quality']['word_count'] for t in tests)
        
        print(f"  T={temp:.1f} : {len(tests)} tests")
        print(f"         Mots: {avg_words:.0f} (min={min_words}, max={max_words})")


def export_csv(report: Dict, output_file: Path):
    """Exporte les résultats en CSV pour analyse externe."""
    import csv
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # En-têtes
        headers = ['test_id', 'success', 'temperature', 'max_tokens', 'top_p', 
                   'repeat_penalty', 'word_count', 'num_parts', 'estimated_duration']
        writer.writerow(headers)
        
        # Données
        for test in report['tests']:
            row = [
                test['test_id'],
                test['success'],
                test['params'].get('temperature', ''),
                test['params'].get('max_tokens', ''),
                test['params'].get('top_p', ''),
                test['params'].get('repeat_penalty', ''),
                test.get('quality', {}).get('word_count', ''),
                test.get('quality', {}).get('num_parts', ''),
                test.get('quality', {}).get('estimated_duration', '')
            ]
            writer.writerow(row)
    
    print(f"\n✓ Export CSV: {output_file}")


def main():
    """Analyse les résultats du gridsearch."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_gridsearch.py output/gridsearch/run_YYYYMMDD_HHMMSS")
        
        # Lister les runs disponibles
        gridsearch_dir = Path("output/gridsearch")
        if gridsearch_dir.exists():
            runs = sorted(gridsearch_dir.glob("run_*"))
            if runs:
                print("\nRuns disponibles:")
                for run in runs[-5:]:  # 5 derniers
                    print(f"  - {run.name}")
        sys.exit(1)
    
    run_dir = Path(sys.argv[1])
    
    if not run_dir.exists():
        print(f"Erreur: Dossier non trouvé: {run_dir}")
        sys.exit(1)
    
    # Charger résultats
    print(f"\nChargement des résultats depuis: {run_dir}")
    report = load_gridsearch_results(run_dir)
    
    if not report:
        sys.exit(1)
    
    # Analyses
    print_summary(report)
    analyze_by_parameter(report)
    find_best_config(report)
    compare_temperatures(report)
    
    # Export CSV
    csv_file = run_dir / "results.csv"
    export_csv(report, csv_file)
    
    print("\n" + "="*80)
    print("ANALYSE TERMINÉE")
    print("="*80)
    print(f"\nRapport complet: {run_dir / 'comparison_report.txt'}")
    print(f"Données CSV: {csv_file}")
    print(f"Résultats individuels: {run_dir / 'test_XXX/'}")
    print()


if __name__ == '__main__':
    main()
