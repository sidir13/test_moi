"""
Tests for Orchestrator
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
        yield


def test_orchestrator_import():
    """Test that Orchestrator can be imported."""
    from orchestrator import ScenarioMakerOrchestrator
    assert ScenarioMakerOrchestrator is not None


def test_orchestrator_initialization(mock_env):
    """Test Orchestrator initialization."""
    with patch('orchestrator.ClaudeClient'):
        with patch('orchestrator.SkillLoader'):
            from orchestrator import ScenarioMakerOrchestrator
            
            orchestrator = ScenarioMakerOrchestrator(log_level="ERROR")
            
            assert orchestrator.agents is not None
            assert orchestrator.skills is not None


def test_list_available_skills(mock_env):
    """Test listing available skills."""
    with patch('orchestrator.ClaudeClient'):
        with patch('orchestrator.SkillLoader') as mock_loader:
            mock_loader.load_all_skills.return_value = {
                'agent_0_request_parser': {'instance': Mock(), 'config': {}}
            }
            
            from orchestrator import ScenarioMakerOrchestrator
            
            orchestrator = ScenarioMakerOrchestrator(log_level="ERROR")
            skills_list = orchestrator.list_available_skills()
            
            assert 'agents' in skills_list
            assert 'skills' in skills_list
