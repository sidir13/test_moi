"""
Tests for Skills
"""

import pytest
from unittest.mock import Mock


def test_historical_analyzer_import():
    """Test importing historical analyzer."""
    from skills.historical_context_analyzer import HistoricalContextAnalyzer
    assert HistoricalContextAnalyzer is not None


def test_historical_analyzer_initialization():
    """Test historical analyzer initialization."""
    from skills.historical_context_analyzer import HistoricalContextAnalyzer
    
    mock_client = Mock()
    analyzer = HistoricalContextAnalyzer(mock_client)
    
    assert analyzer.model == "claude-sonnet-4-5"
    assert analyzer.temperature == 0.2


def test_detect_anachronisms():
    """Test anachronism detection."""
    from skills.historical_context_analyzer import HistoricalContextAnalyzer
    
    mock_client = Mock()
    analyzer = HistoricalContextAnalyzer(mock_client)
    
    text = "En 1905, ils utilisaient internet et des smartphones"
    result = analyzer.detect_anachronisms(text, 1905)
    
    assert 'anachronisms_found' in result
    assert len(result['anachronisms_found']) > 0
    assert result['score'] < 1.0


def test_sound_selector_import():
    """Test importing sound selector."""
    from skills.ambiance_sound_selector import AmbianceSoundSelector
    assert AmbianceSoundSelector is not None


def test_sound_selector_initialization():
    """Test sound selector initialization."""
    from skills.ambiance_sound_selector import AmbianceSoundSelector
    
    mock_client = Mock()
    selector = AmbianceSoundSelector(mock_client)
    
    assert selector.mood_compatibility is not None


def test_calculate_sound_relevance():
    """Test sound relevance calculation."""
    from skills.ambiance_sound_selector import AmbianceSoundSelector
    
    mock_client = Mock()
    selector = AmbianceSoundSelector(mock_client)
    
    sound = {
        'tags': ['port', 'ambiance', 'morning'],
        'duration': 120,
        'metadata': {
            'mood': 'calm',
            'period': '1900s'
        }
    }
    
    criteria = {
        'required_tags': ['port', 'ambiance'],
        'mood': 'calm',
        'period': '1900s',
        'duration_target': 100
    }
    
    result = selector.calculate_sound_relevance(sound, criteria)
    
    assert 'relevance_score' in result
    assert 'breakdown' in result
    assert 0 <= result['relevance_score'] <= 1


def test_timeline_composer_import():
    """Test importing timeline composer."""
    from skills.audio_timeline_composer import AudioTimelineComposer
    assert AudioTimelineComposer is not None


def test_voice_matcher_import():
    """Test importing voice matcher."""
    from skills.voice_persona_matcher import VoicePersonaMatcher
    assert VoicePersonaMatcher is not None


def test_voice_matcher_profile():
    """Test voice profile matching."""
    from skills.voice_persona_matcher import VoicePersonaMatcher
    
    mock_client = Mock()
    matcher = VoicePersonaMatcher(mock_client)
    
    profile = matcher.match_voice_profile({}, 'dramatique_immersif')
    
    assert 'gender' in profile
    assert 'age_range' in profile
    assert 'accent' in profile
