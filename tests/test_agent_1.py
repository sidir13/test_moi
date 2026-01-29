"""
Tests for Agent 1: Narrative Structure Architect
"""

import pytest
from unittest.mock import Mock


def test_agent_1_import():
    """Test that Agent 1 can be imported."""
    from agents.agent_1_structure import StructureArchitectAgent
    assert StructureArchitectAgent is not None


def test_agent_1_initialization():
    """Test Agent 1 initialization."""
    from agents.agent_1_structure import StructureArchitectAgent
    
    mock_client = Mock()
    agent = StructureArchitectAgent(mock_client)
    
    assert agent.model == "claude-sonnet-4-5"
    assert agent.temperature == 0.7


def test_calculate_parts_distribution():
    """Test parts duration distribution calculation."""
    from agents.agent_1_structure import StructureArchitectAgent
    
    mock_client = Mock()
    agent = StructureArchitectAgent(mock_client)
    
    # Test 120s duration
    parts = agent.calculate_parts_distribution(120, 'grand_public', 'modere', 'chronologique')
    assert isinstance(parts, list)
    assert len(parts) == 3
    assert sum(parts) == pytest.approx(120, rel=0.01)


def test_define_emotional_arc():
    """Test emotional arc definition."""
    from agents.agent_1_structure import StructureArchitectAgent
    
    mock_client = Mock()
    agent = StructureArchitectAgent(mock_client)
    
    arc = agent.define_emotional_arc('dramatique_immersif', 'chronologique', 180, 'grand_public')
    
    assert 'type' in arc
    assert 'points_cles' in arc
    assert isinstance(arc['points_cles'], list)
    assert len(arc['points_cles']) > 0


def test_parts_distribution_for_children():
    """Test that children get shorter parts."""
    from agents.agent_1_structure import StructureArchitectAgent
    
    mock_client = Mock()
    agent = StructureArchitectAgent(mock_client)
    
    # Children should get more parts (shorter each)
    parts_children = agent.calculate_parts_distribution(180, 'enfants', 'modere', 'chronologique')
    parts_adult = agent.calculate_parts_distribution(180, 'grand_public', 'modere', 'chronologique')
    
    # Children should have more parts (shorter durations)
    assert len(parts_children) >= len(parts_adult)
