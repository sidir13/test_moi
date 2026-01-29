"""
Initialize sound library index.
Scans sound_library directory and generates index.json with metadata.
"""

import json
import os
from pathlib import Path
from typing import List, Dict


def scan_sound_library(library_path: str = "./data/sound_library") -> List[Dict]:
    """
    Scan sound library directory and create index.
    
    Args:
        library_path: Path to sound library
        
    Returns:
        List of sound entries
    """
    lib_path = Path(library_path)
    sounds = []
    
    # Scan for audio files
    audio_extensions = ['.wav', '.mp3', '.ogg', '.flac']
    
    for audio_file in lib_path.rglob('*'):
        if audio_file.suffix.lower() in audio_extensions:
            # Get relative path
            relative_path = audio_file.relative_to(lib_path)
            
            # Extract basic metadata from path
            parts = relative_path.parts
            category = parts[0] if len(parts) > 1 else 'other'
            
            # Basic tags from filename and path
            tags = [
                category,
                audio_file.stem.lower()
            ]
            
            sound_entry = {
                'file': str(relative_path).replace('\\', '/'),
                'tags': tags,
                'duration': 0.0,  # Would extract with librosa/pydub
                'metadata': {
                    'period': 'generic',
                    'mood': 'neutral',
                    'quality': 'medium',
                    'description': f'Audio file: {audio_file.name}',
                    'source': 'Local library'
                }
            }
            
            sounds.append(sound_entry)
    
    return sounds


def create_index(library_path: str = "./data/sound_library", output_file: str = None):
    """
    Create sound library index file.
    
    Args:
        library_path: Path to sound library
        output_file: Output JSON file path (defaults to library_path/index.json)
    """
    from datetime import datetime
    
    if not output_file:
        output_file = os.path.join(library_path, 'index.json')
    
    print(f"Scanning sound library: {library_path}")
    sounds = scan_sound_library(library_path)
    
    index = {
        'version': '1.0',
        'last_updated': datetime.now().isoformat(),
        'total_sounds': len(sounds),
        'sounds': sounds
    }
    
    # Create directory if needed
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    
    # Write index
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Index created: {output_file}")
    print(f"  Total sounds: {len(sounds)}")


if __name__ == '__main__':
    import sys
    
    library_path = sys.argv[1] if len(sys.argv) > 1 else './data/sound_library'
    create_index(library_path)
