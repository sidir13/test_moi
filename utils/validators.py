"""
Validation utilities for configurations and scenarios.
"""

import re
from typing import Dict, List, Tuple, Any
from datetime import datetime


class ConfigValidator:
    """Validates scenario configurations."""
    
    @staticmethod
    def validate_duration(duration: int, min_dur: int = 60, max_dur: int = 600) -> Tuple[bool, List[str]]:
        """
        Validate duration is within acceptable range.
        
        Args:
            duration: Duration in seconds
            min_dur: Minimum duration
            max_dur: Maximum duration
            
        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []
        
        if duration < min_dur:
            errors.append(f"Duration {duration}s is below minimum {min_dur}s")
        elif duration > max_dur:
            errors.append(f"Duration {duration}s exceeds maximum {max_dur}s")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_temperature(temp: float) -> Tuple[bool, List[str]]:
        """Validate model temperature."""
        errors = []
        
        if not 0.0 <= temp <= 1.0:
            errors.append(f"Temperature {temp} must be between 0.0 and 1.0")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_config_consistency(config: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        Validate configuration consistency.
        
        Returns:
            Tuple of (is_valid, list of errors, list of warnings)
        """
        errors = []
        warnings = []
        
        # Check for child-friendly content with inappropriate tone
        public = config.get('generation_parameters', {}).get('public_cible', {}).get('value')
        ton = config.get('generation_parameters', {}).get('ton', {}).get('value')
        
        if public in ['enfants', 'scolaire_primaire']:
            if ton in ['dramatique_immersif', 'emotionnel_personnel']:
                warnings.append(
                    f"Tone '{ton}' may be too intense for audience '{public}'. "
                    "Consider 'pedagogique_accessible'"
                )
        
        # Check duration vs number of parts logic
        duree = config.get('generation_parameters', {}).get('duree', {}).get('value', 120)
        if duree < 60:
            warnings.append("Very short duration may limit narrative depth")
        
        # Check balance narration/archives
        balance = config.get('generation_parameters', {}).get('equilibre_narration_archives', {}).get('value', 0.6)
        if balance < 0.3:
            warnings.append("Low narration balance may result in archive-heavy output")
        elif balance > 0.9:
            warnings.append("High narration balance may underutilize provided archives")
        
        return len(errors) == 0, errors, warnings


class HistoricalValidator:
    """Validates historical accuracy."""
    
    # Common anachronistic words for different periods
    ANACHRONISMS = {
        1900: [
            'ordinateur', 'internet', 'télévision', 'avion',  # Technology
            'smartphone', 'digital', 'virtuel', 'en ligne',
            'globalisation', 'mondialisation'  # Modern concepts
        ],
        1950: [
            'ordinateur personnel', 'internet', 'portable', 'smartphone',
            'numérique', 'digital', 'virtuel', 'en ligne'
        ]
    }
    
    @staticmethod
    def detect_anachronisms(text: str, period_start: int) -> List[str]:
        """
        Detect anachronistic words in text.
        
        Args:
            text: Text to analyze
            period_start: Start year of period
            
        Returns:
            List of detected anachronisms
        """
        text_lower = text.lower()
        detected = []
        
        # Find closest period in our dictionary
        relevant_period = min(
            HistoricalValidator.ANACHRONISMS.keys(),
            key=lambda x: abs(x - period_start)
        )
        
        for word in HistoricalValidator.ANACHRONISMS[relevant_period]:
            if word.lower() in text_lower:
                detected.append(word)
        
        return detected
    
    @staticmethod
    def validate_dates(text: str, period: Dict[str, int]) -> List[str]:
        """
        Validate dates mentioned in text are within period.
        
        Args:
            text: Text to analyze
            period: Dict with 'start_year' and 'end_year'
            
        Returns:
            List of errors for dates outside period
        """
        errors = []
        
        # Pattern to find years (4 digits)
        year_pattern = r'\b(1[0-9]{3}|20[0-9]{2})\b'
        years = re.findall(year_pattern, text)
        
        start = period.get('start_year', 1900)
        end = period.get('end_year', 2000)
        
        for year_str in years:
            year = int(year_str)
            if year < start or year > end:
                errors.append(f"Date {year} is outside period {start}-{end}")
        
        return errors
    
    @staticmethod
    def validate_scenario(scenario: Dict[str, Any], period: Dict[str, int]) -> Dict[str, Any]:
        """
        Comprehensive validation of scenario historical accuracy.
        
        Args:
            scenario: Scenario dict
            period: Period dict
            
        Returns:
            Validation result dict
        """
        errors = []
        warnings = []
        
        # Extract all text from scenario
        text_parts = []
        for partie in scenario.get('parties', []):
            text_parts.append(partie.get('texte_narration', ''))
        
        full_text = ' '.join(text_parts)
        
        # Check dates
        date_errors = HistoricalValidator.validate_dates(full_text, period)
        errors.extend(date_errors)
        
        # Check anachronisms
        anachronisms = HistoricalValidator.detect_anachronisms(
            full_text,
            period.get('start_year', 1900)
        )
        if anachronisms:
            warnings.extend([f"Possible anachronism: {word}" for word in anachronisms])
        
        # Calculate accuracy score (1.0 = perfect, decreases with issues)
        accuracy_score = 1.0
        accuracy_score -= len(errors) * 0.1  # Major issues
        accuracy_score -= len(warnings) * 0.05  # Minor issues
        accuracy_score = max(0.0, min(1.0, accuracy_score))
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'accuracy_score': accuracy_score
        }
