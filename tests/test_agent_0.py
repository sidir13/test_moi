"""
Tests for Agent 0: Request Parser
"""

import pytest
import json
from unittest.mock import Mock, MagicMock


def test_agent_0_import():
    """Test that Agent 0 can be imported."""
    from agents.agent_0_request_parser import RequestParserAgent
    assert RequestParserAgent is not None


def test_agent_0_initialization():
    """Test Agent 0 initialization."""
    from agents.agent_0_request_parser import RequestParserAgent
    
    mock_client = Mock()
    agent = RequestParserAgent(mock_client)
    
    assert agent.model == "claude-sonnet-4-5"
    assert agent.temperature == 0.1
    assert agent.max_tokens == 6000


def test_validate_configuration():
    """Test configuration validation."""
    from agents.agent_0_request_parser import RequestParserAgent
    
    mock_client = Mock()
    agent = RequestParserAgent(mock_client)
    
    # Test with minimal valid config
    config = {
        'scenario_config': {
            'generation_parameters': {
                'duree': {'value': 120},
                'public_cible': {'value': 'grand_public'},
                'ton': {'value': 'neutre_informatif'},
                'equilibre_narration_archives': {'value': 0.6}
            }
        }
    }
    
    result = agent.validate_configuration(config)
    assert result['valid'] == True
    assert isinstance(result['warnings'], list)


def test_generate_summary():
    """Test summary generation."""
    from agents.agent_0_request_parser import RequestParserAgent
    
    mock_client = Mock()
    agent = RequestParserAgent(mock_client)
    
    config = {
        'scenario_config': {
            'generation_parameters': {
                'forme': {'value': 'documentaire'},
                'duree': {'value': 180},
                'ton': {'value': 'dramatique_immersif'},
                'public_cible': {'value': 'grand_public'},
                'nombre_scenarios': {'value': 3}
            },
            'historical_context': {
                'period': {'start_year': 1900, 'end_year': 1910},
                'location': {'primary': 'Port'},
                'themes': {'primary': ['grèves']}
            }
        }
    }
    
    summary = agent.generate_summary(config)
    assert isinstance(summary, str)
    assert 'documentaire' in summary.lower()
    assert '180' in summary


def test_merge_expert_config():
    """Test merging expert config with defaults."""
    from agents.agent_0_request_parser import RequestParserAgent
    
    mock_client = Mock()
    agent = RequestParserAgent(mock_client)
    
    default_config = {
        'scenario_config': {
            'generation_parameters': {
                'duree': {'value': 120, 'user_specified': False}
            }
        }
    }
    
    user_config = {
        'scenario_config': {
            'generation_parameters': {
                'duree': {'value': 300, 'user_specified': True}
            }
        }
    }
    
    result = agent.merge_expert_config(user_config, default_config)
    assert result['scenario_config']['generation_parameters']['duree']['value'] == 300
