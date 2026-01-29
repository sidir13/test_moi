"""Voice Persona Matcher Skill"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class VoicePersonaMatcher:
    """Matches voice profiles to narrative needs."""
    
    def __init__(self, client):
        self.client = client
        logger.info("VoicePersonaMatcher initialized")
    
    def match_voice_profile(
        self,
        persona: Dict,
        tone: str,
        age_period: Optional[str] = None
    ) -> Dict[str, str]:
        """Match optimal voice profile."""
        
        # Default profile
        profile = {
            'gender': 'male',
            'age_range': '45-55',
            'accent': 'regional',
            'timbre': 'medium',
            'delivery': 'moderate'
        }
        
        # Adjust based on tone
        if tone in ['dramatique_immersif', 'emotionnel_personnel']:
            profile['delivery'] = 'expressive'
            profile['timbre'] = 'rich'
        elif tone in ['pedagogique_accessible', 'contemplatif']:
            profile['delivery'] = 'calm'
            profile['timbre'] = 'warm'
        
        return profile
