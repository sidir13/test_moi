"""Script pour vérifier les imports manquants dans le projet."""

import os
import re
from pathlib import Path

def check_file_for_missing_imports(file_path):
    """Vérifie si un fichier utilise Optional/List/Dict sans les importer."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        issues = []
        
        # Vérifier les imports existants
        has_typing_import = 'from typing import' in content
        imported_types = set()
        
        if has_typing_import:
            # Extraire ce qui est importé
            import_match = re.search(r'from typing import ([^\n]+)', content)
            if import_match:
                imports = import_match.group(1)
                imported_types = {t.strip() for t in imports.split(',')}
        
        # Vérifier l'utilisation de types courants
        uses_optional = re.search(r'\bOptional\[', content)
        uses_list = re.search(r'\bList\[', content)
        uses_dict = re.search(r'\bDict\[', content)
        uses_tuple = re.search(r'\bTuple\[', content)
        uses_union = re.search(r'\bUnion\[', content)
        
        if uses_optional and 'Optional' not in imported_types:
            issues.append('Optional utilisé mais non importé')
        if uses_list and 'List' not in imported_types:
            issues.append('List utilisé mais non importé')
        if uses_dict and 'Dict' not in imported_types:
            issues.append('Dict utilisé mais non importé')
        if uses_tuple and 'Tuple' not in imported_types:
            issues.append('Tuple utilisé mais non importé')
        if uses_union and 'Union' not in imported_types:
            issues.append('Union utilisé mais non importé')
        
        return issues
    except Exception as e:
        return [f"Erreur lecture fichier: {e}"]

def scan_directory(directory):
    """Scan un répertoire pour les fichiers Python."""
    issues_found = {}
    
    for root, dirs, files in os.walk(directory):
        # Ignorer certains dossiers
        dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.git', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                issues = check_file_for_missing_imports(file_path)
                if issues:
                    issues_found[file_path] = issues
    
    return issues_found

if __name__ == '__main__':
    print("Verification des imports manquants...\n")
    
    directories = ['agents', 'skills', 'utils', 'models']
    all_issues = {}
    
    for directory in directories:
        if os.path.exists(directory):
            print(f"Scan de {directory}/...")
            issues = scan_directory(directory)
            all_issues.update(issues)
    
    if all_issues:
        print(f"\n[!] {len(all_issues)} fichier(s) avec des imports manquants :\n")
        for file_path, issues in all_issues.items():
            print(f"- {file_path}")
            for issue in issues:
                print(f"  x {issue}")
            print()
    else:
        print("\n[OK] Aucun import manquant detecte !")
    
    print(f"Total: {len(all_issues)} fichier(s) a corriger")
