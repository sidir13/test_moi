"""
Skill loader for loading Claude agent skills from skill.md files.
"""

import re
import importlib
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SkillLoader:
    """Loads skills from skill.md files and their Python implementations."""
    
    @staticmethod
    def parse_skill_md(skill_md_path: Path) -> Dict[str, Any]:
        """
        Parse a skill.md file and extract configuration.
        
        Args:
            skill_md_path: Path to skill.md file
            
        Returns:
            Dict with skill configuration:
            {
                'name': str,
                'role': str,
                'model': str,
                'temperature': float,
                'max_tokens': int,
                'system_prompt': str (optional),
                'python_tools': bool,
                'functions': list of function dicts
            }
        """
        if not skill_md_path.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_md_path}")
        
        content = skill_md_path.read_text(encoding='utf-8')
        
        config = {
            'name': '',
            'role': '',
            'model': 'claude-sonnet-4-5',
            'temperature': 0.7,
            'max_tokens': 4096,
            'system_prompt': None,
            'python_tools': False,
            'functions': []
        }
        
        # Extract name from first heading
        name_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if name_match:
            config['name'] = name_match.group(1).strip()
        
        # Extract role
        role_match = re.search(r'##\s+Role\s+(.+?)(?=##|\Z)', content, re.DOTALL)
        if role_match:
            config['role'] = role_match.group(1).strip()
        
        # Extract model configuration
        model_config = re.search(
            r'##\s+Model Configuration\s+(.+?)(?=##|\Z)',
            content,
            re.DOTALL
        )
        if model_config:
            model_text = model_config.group(1)
            
            # Extract model name
            model_match = re.search(r'-\s+Model:\s*(.+)', model_text)
            if model_match:
                config['model'] = model_match.group(1).strip()
            
            # Extract temperature
            temp_match = re.search(r'-\s+Temperature:\s*([\d.]+)', model_text)
            if temp_match:
                config['temperature'] = float(temp_match.group(1))
            
            # Extract max tokens
            tokens_match = re.search(r'-\s+Max tokens:\s*(\d+)', model_text)
            if tokens_match:
                config['max_tokens'] = int(tokens_match.group(1))
        
        # Extract system prompt
        system_match = re.search(
            r'##\s+System Prompt\s+(.+?)(?=##|\Z)',
            content,
            re.DOTALL
        )
        if system_match:
            config['system_prompt'] = system_match.group(1).strip()
        
        # Extract Python tools flag
        python_tools = re.search(r'##\s+Python Tools.*?Enabled[:\s]+([Tt]rue|[Yy]es|Oui)', content, re.DOTALL)
        if python_tools:
            config['python_tools'] = True
        
        # Extract functions
        functions_section = re.search(
            r'##\s+Functions\s+(.+?)(?=##\s+(?!#)|$)',
            content,
            re.DOTALL
        )
        if functions_section:
            functions_text = functions_section.group(1)
            
            # Find all function definitions (### function_name)
            function_blocks = re.finditer(
                r'###\s+(\w+)\s+(.+?)(?=###|\Z)',
                functions_text,
                re.DOTALL
            )
            
            for func_match in function_blocks:
                func_name = func_match.group(1)
                func_body = func_match.group(2)
                
                # Extract input/output
                input_match = re.search(r'\*\*Input\*\*\s*:\s*`(.+?)`', func_body)
                output_match = re.search(r'\*\*Output\*\*\s*:\s*(.+?)(?=\*\*|\n\n|\Z)', func_body, re.DOTALL)
                
                func_config = {
                    'name': func_name,
                    'input': input_match.group(1) if input_match else '',
                    'output': output_match.group(1).strip() if output_match else '',
                    'description': func_body.split('\n')[0].strip()
                }
                
                config['functions'].append(func_config)
        
        logger.info(f"Parsed skill: {config['name']} ({config['model']}, temp={config['temperature']})")
        return config
    
    @staticmethod
    def load_skill_module(
        skill_dir: Path,
        skill_config: Dict[str, Any],
        client: Any
    ) -> Any:
        """
        Load and instantiate the Python skill module.
        
        Args:
            skill_dir: Path to skill directory
            skill_config: Skill configuration from parse_skill_md
            client: Claude client instance to pass to skill
            
        Returns:
            Instantiated skill class
        """
        # Find Python file in skill directory
        python_files = list(skill_dir.glob('*.py'))
        python_files = [f for f in python_files if f.name != '__init__.py']
        
        if not python_files:
            raise FileNotFoundError(f"No Python implementation found in {skill_dir}")
        
        if len(python_files) > 1:
            logger.warning(f"Multiple Python files in {skill_dir}, using first: {python_files[0]}")
        
        python_file = python_files[0]
        
        # Construct module path
        # E.g., agents/agent_0_request_parser/parser.py -> agents.agent_0_request_parser.parser
        parts = list(skill_dir.parts)
        if parts[0] == '.':
            parts = parts[1:]
        
        module_path = '.'.join(parts) + '.' + python_file.stem
        
        try:
            module = importlib.import_module(module_path)
            
            # Find the main class (first class that isn't a base class)
            # Assumes class name follows pattern: SomethingAgent or SomethingSkill
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    (attr_name.endswith('Agent') or attr_name.endswith('Skill') or
                     attr_name.endswith('Analyzer') or attr_name.endswith('Selector') or
                     attr_name.endswith('Builder') or attr_name.endswith('Matcher') or
                     attr_name.endswith('Composer'))):
                    
                    # Instantiate with client
                    skill_instance = attr(client)
                    logger.info(f"Loaded skill class: {attr_name} from {module_path}")
                    return skill_instance
            
            raise ValueError(f"No suitable skill class found in {module_path}")
            
        except ImportError as e:
            logger.error(f"Failed to import {module_path}: {e}")
            raise
    
    @staticmethod
    def load_all_skills(
        base_dir: Path,
        client: Any,
        skill_type: str = "skills"
    ) -> Dict[str, Any]:
        """
        Load all skills from a directory (agents/ or skills/).
        
        Args:
            base_dir: Base directory containing skill folders
            client: Claude client instance
            skill_type: Type of skills being loaded ("agents" or "skills")
            
        Returns:
            Dict mapping skill names to skill instances
        """
        skills = {}
        
        if not base_dir.exists():
            logger.warning(f"Skill directory does not exist: {base_dir}")
            return skills
        
        for skill_dir in base_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_md = skill_dir / 'skill.md'
            if not skill_md.exists():
                logger.warning(f"No skill.md found in {skill_dir}, skipping")
                continue
            
            try:
                # Parse skill configuration
                skill_config = SkillLoader.parse_skill_md(skill_md)
                
                # Load Python implementation
                skill_instance = SkillLoader.load_skill_module(
                    skill_dir,
                    skill_config,
                    client
                )
                
                # Store with directory name as key
                skills[skill_dir.name] = {
                    'instance': skill_instance,
                    'config': skill_config
                }
                
                logger.info(f"Successfully loaded {skill_type}: {skill_dir.name}")
                
            except Exception as e:
                logger.error(f"Failed to load skill from {skill_dir}: {e}", exc_info=True)
        
        return skills
