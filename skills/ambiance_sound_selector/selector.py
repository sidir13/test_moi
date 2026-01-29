"""
Ambiance Sound Selector Skill
Selects optimal sounds from sound library.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class AmbianceSoundSelector:
    """Selects sounds from library based on criteria."""
    
    def __init__(self, client):
        """
        Initialize the selector.
        
        Args:
            client: Claude client instance (not used for this skill)
        """
        self.client = client
        
        # Mood compatibility matrix
        self.mood_compatibility = {
            'calm': ['peaceful', 'quiet', 'serene', 'calm'],
            'tense': ['anxious', 'worried', 'uneasy', 'tense'],
            'busy': ['active', 'crowded', 'energetic', 'busy'],
            'dramatic': ['intense', 'powerful', 'emotional', 'dramatic'],
            'contemplative': ['calm', 'peaceful', 'reflective', 'contemplative']
        }
        
        logger.info("AmbianceSoundSelector initialized")
    
    def search_sound_library(
        self,
        tags: List[str],
        filters: Optional[Dict] = None,
        library_path: str = "./data/sound_library"
    ) -> Dict[str, Any]:
        """
        Search sound library by tags and filters.
        
        Args:
            tags: Required tags
            filters: Additional filters
            library_path: Path to sound library
            
        Returns:
            Dict with candidates list
        """
        logger.info(f"Searching sound library for tags: {tags}")
        
        filters = filters or {}
        lib_path = Path(library_path)
        index_path = lib_path / "index.json"
        
        # Load index
        if not index_path.exists():
            logger.warning(f"Sound library index not found: {index_path}")
            return {'candidates': [], 'total_found': 0}
        
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                index = json.load(f)
        except Exception as e:
            logger.error(f"Error loading sound library index: {e}")
            return {'candidates': [], 'total_found': 0}
        
        # Filter sounds
        candidates = []
        for sound in index.get('sounds', []):
            if self._matches_criteria(sound, tags, filters):
                candidates.append(sound)
        
        # Sort by relevance (basic)
        candidates.sort(
            key=lambda s: len(set(s.get('tags', [])) & set(tags)),
            reverse=True
        )
        
        logger.info(f"Found {len(candidates)} matching sounds")
        return {
            'candidates': candidates,
            'total_found': len(candidates)
        }
    
    def calculate_sound_relevance(
        self,
        sound: Dict,
        criteria: Dict
    ) -> Dict[str, Any]:
        """
        Calculate relevance score for a sound.
        
        Args:
            sound: Sound candidate
            criteria: Criteria dict
            
        Returns:
            Relevance result
        """
        required_tags = criteria.get('required_tags', [])
        mood = criteria.get('mood', '')
        period = criteria.get('period', '')
        duration_target = criteria.get('duration_target', 0)
        weights = criteria.get('weights', {
            'tags': 0.4,
            'mood': 0.3,
            'period': 0.2,
            'duration': 0.1
        })
        
        # Calculate individual scores
        tags_score = self._calculate_tags_score(sound, required_tags)
        mood_score = self._calculate_mood_score(sound, mood)
        period_score = self._calculate_period_score(sound, period)
        duration_score = self._calculate_duration_score(sound, duration_target)
        
        # Weighted average
        relevance_score = (
            tags_score * weights.get('tags', 0.4) +
            mood_score * weights.get('mood', 0.3) +
            period_score * weights.get('period', 0.2) +
            duration_score * weights.get('duration', 0.1)
        )
        
        reasoning = f"Tags: {tags_score:.2f}, Mood: {mood_score:.2f}, Period: {period_score:.2f}, Duration: {duration_score:.2f}"
        
        return {
            'relevance_score': relevance_score,
            'breakdown': {
                'tags_score': tags_score,
                'mood_score': mood_score,
                'period_score': period_score,
                'duration_score': duration_score
            },
            'reasoning': reasoning
        }
    
    def select_optimal_sound(
        self,
        candidates: List[Dict],
        criteria: Dict,
        return_alternatives: bool = False
    ) -> Dict[str, Any]:
        """
        Select optimal sound from candidates.
        
        Args:
            candidates: List of candidate sounds
            criteria: Selection criteria
            return_alternatives: Return alternative sounds
            
        Returns:
            Selected sound with alternatives if requested
        """
        if not candidates:
            logger.warning("No candidates to select from")
            return {'selected': None, 'alternatives': []}
        
        # Score all candidates
        scored = []
        for candidate in candidates:
            relevance = self.calculate_sound_relevance(candidate, criteria)
            scored.append({
                'sound': candidate,
                'score': relevance['relevance_score'],
                'breakdown': relevance['breakdown']
            })
        
        # Sort by score
        scored.sort(key=lambda x: x['score'], reverse=True)
        
        # Select best
        best = scored[0]
        
        result = {
            'selected': {
                'file': best['sound'].get('file'),
                'relevance_score': best['score'],
                'metadata': best['sound'].get('metadata', {})
            }
        }
        
        if return_alternatives and len(scored) > 1:
            result['alternatives'] = [
                {
                    'file': s['sound'].get('file'),
                    'relevance_score': s['score']
                }
                for s in scored[1:4]  # Top 3 alternatives
            ]
        else:
            result['alternatives'] = []
        
        logger.info(f"Selected: {result['selected']['file']} (score: {best['score']:.2f})")
        return result
    
    def get_sound_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from audio file.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Metadata dict
        """
        path = Path(file_path)
        
        if not path.exists():
            logger.warning(f"Sound file not found: {file_path}")
            return {}
        
        # Basic metadata (would use librosa/pydub in production)
        try:
            file_size = path.stat().st_size
            
            return {
                'duration': 0.0,  # Would extract with audio library
                'sample_rate': 48000,  # Default assumption
                'channels': 2,
                'format': path.suffix.upper().replace('.', ''),
                'bit_depth': 24,  # Default assumption
                'file_size': file_size
            }
        except Exception as e:
            logger.error(f"Error getting metadata: {e}")
            return {}
    
    def _matches_criteria(
        self,
        sound: Dict,
        required_tags: List[str],
        filters: Dict
    ) -> bool:
        """Check if sound matches criteria."""
        # Check tags (intersection)
        sound_tags = set(sound.get('tags', []))
        required_tags_set = set(required_tags)
        
        if not required_tags_set.issubset(sound_tags):
            return False
        
        # Check filters
        metadata = sound.get('metadata', {})
        
        # Period filter
        if 'period' in filters:
            if metadata.get('period') != filters['period']:
                return False
        
        # Mood filter
        if 'mood' in filters:
            if metadata.get('mood') != filters['mood']:
                return False
        
        # Min duration filter
        if 'min_duration' in filters:
            if sound.get('duration', 0) < filters['min_duration']:
                return False
        
        # Quality filter
        if 'quality' in filters:
            if metadata.get('quality') != filters['quality']:
                return False
        
        return True
    
    def _calculate_tags_score(self, sound: Dict, required_tags: List[str]) -> float:
        """Calculate tags match score."""
        if not required_tags:
            return 1.0
        
        sound_tags = set(sound.get('tags', []))
        required_set = set(required_tags)
        matched = len(required_set & sound_tags)
        
        return matched / len(required_tags)
    
    def _calculate_mood_score(self, sound: Dict, mood: str) -> float:
        """Calculate mood match score."""
        if not mood:
            return 1.0
        
        sound_mood = sound.get('metadata', {}).get('mood', '')
        
        if sound_mood == mood:
            return 1.0
        
        # Check compatibility
        compatible_moods = self.mood_compatibility.get(mood, [])
        if sound_mood in compatible_moods:
            return 0.7
        
        return 0.3
    
    def _calculate_period_score(self, sound: Dict, period: str) -> float:
        """Calculate period match score."""
        if not period:
            return 1.0
        
        sound_period = sound.get('metadata', {}).get('period', '')
        
        if sound_period == period:
            return 1.0
        
        # Close periods (e.g., 1900s vs 1910s)
        if sound_period and abs(self._period_to_year(sound_period) - self._period_to_year(period)) <= 20:
            return 0.8
        
        # Generic/timeless
        if sound_period == 'generic':
            return 0.5
        
        return 0.3
    
    def _calculate_duration_score(self, sound: Dict, duration_target: float) -> float:
        """Calculate duration match score."""
        if duration_target == 0:
            return 1.0
        
        sound_duration = sound.get('duration', 0)
        
        if sound_duration >= duration_target:
            return 1.0
        
        return sound_duration / duration_target
    
    def _period_to_year(self, period: str) -> int:
        """Convert period string to year."""
        import re
        match = re.search(r'(\d{4})', period)
        if match:
            return int(match.group(1))
        return 1900  # Default
