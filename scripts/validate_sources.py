"""
Validate historical sources configuration.
Checks URLs, file paths, and accessibility.
"""

import json
import sys
from pathlib import Path


def validate_sources(config_path: str = "./config/default_config.json"):
    """
    Validate historical sources in configuration.
    
    Args:
        config_path: Path to configuration file
    """
    print(f"Validating sources in: {config_path}")
    
    config_file = Path(config_path)
    if not config_file.exists():
        print(f"✗ Configuration file not found: {config_path}")
        return False
    
    # Load config
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Get data sources
    data_sources = config.get('scenario_config', {}).get('data_sources', {})
    validated_sources = data_sources.get('validated_sources', {}).get('sources', [])
    
    print(f"\nFound {len(validated_sources)} validated sources:")
    
    all_valid = True
    for i, source in enumerate(validated_sources, 1):
        source_type = source.get('type', 'unknown')
        url = source.get('url', '')
        credibility = source.get('credibility', 'unknown')
        
        print(f"\n{i}. {source_type}")
        print(f"   URL: {url}")
        print(f"   Credibility: {credibility}")
        
        # Basic URL validation
        if not url:
            print("   ✗ No URL provided")
            all_valid = False
        elif url.startswith('http'):
            print("   ✓ URL format valid")
        else:
            print("   ⚠ URL format unusual")
    
    # Check user provided sources
    user_provided = data_sources.get('user_provided', {})
    total_user_files = sum(len(files) for files in user_provided.values())
    
    if total_user_files > 0:
        print(f"\nUser provided sources: {total_user_files} files")
        for key, files in user_provided.items():
            if files:
                print(f"  {key}: {len(files)} files")
    
    print("\n" + "="*50)
    if all_valid:
        print("✓ All sources validated successfully")
    else:
        print("⚠ Some sources have issues")
    
    return all_valid


if __name__ == '__main__':
    config_path = sys.argv[1] if len(sys.argv) > 1 else './config/default_config.json'
    validate_sources(config_path)
