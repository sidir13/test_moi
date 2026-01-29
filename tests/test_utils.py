"""
Tests for utility modules
"""

import pytest
from unittest.mock import Mock, patch


def test_config_validator():
    """Test configuration validator."""
    from utils.validators import ConfigValidator
    
    validator = ConfigValidator()
    
    # Test duration validation
    valid, errors = validator.validate_duration(120, 60, 600)
    assert valid == True
    assert len(errors) == 0
    
    # Test invalid duration
    valid, errors = validator.validate_duration(30, 60, 600)
    assert valid == False
    assert len(errors) > 0


def test_temperature_validation():
    """Test temperature validation."""
    from utils.validators import ConfigValidator
    
    validator = ConfigValidator()
    
    valid, errors = validator.validate_temperature(0.5)
    assert valid == True
    
    valid, errors = validator.validate_temperature(1.5)
    assert valid == False


def test_historical_validator():
    """Test historical validator."""
    from utils.validators import HistoricalValidator
    
    validator = HistoricalValidator()
    
    # Test anachronism detection
    text = "En 1905, les dockers utilisaient des ordinateurs pour gérer les stocks"
    anachronisms = validator.detect_anachronisms(text, 1905)
    
    assert len(anachronisms) > 0
    assert 'ordinateur' in str(anachronisms).lower()


def test_logger_setup():
    """Test logger setup."""
    from utils.logger import setup_logger
    
    logger = setup_logger("test_logger", level="ERROR", use_rich=False)
    assert logger is not None
    assert logger.name == "test_logger"


def test_agent_logger():
    """Test agent logger."""
    from utils.logger import AgentLogger
    
    agent_logger = AgentLogger("Test Agent")
    
    agent_logger.log_start("Test task")
    agent_logger.log_end("Test task", status="success")
    
    metrics = agent_logger.get_metrics()
    assert len(metrics) == 1
    assert metrics[0]['agent'] == "Test Agent"
    assert metrics[0]['status'] == "success"


def test_skill_loader_parse():
    """Test skill loader parsing."""
    from utils.skill_loader import SkillLoader
    from pathlib import Path
    import tempfile
    
    # Create temporary skill.md
    skill_content = """# Test Skill

## Role
Test role

## Model Configuration
- Model: claude-sonnet-4-5
- Temperature: 0.5
- Max tokens: 2000

## Functions

### test_function
Test function description

**Input** : `{"param": str}`
**Output** : Result
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(skill_content)
        temp_path = f.name
    
    try:
        skill_config = SkillLoader.parse_skill_md(Path(temp_path))
        
        assert skill_config['name'] == 'Test Skill'
        assert skill_config['model'] == 'claude-sonnet-4-5'
        assert skill_config['temperature'] == 0.5
        assert skill_config['max_tokens'] == 2000
        assert len(skill_config['functions']) == 1
    finally:
        import os
        os.unlink(temp_path)


def test_claude_client_initialization():
    """Test Claude client initialization."""
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
        from utils.claude_client import ClaudeClient
        
        client = ClaudeClient(api_key='test-key')
        assert client.api_key == 'test-key'
        assert client.max_retries == 3
