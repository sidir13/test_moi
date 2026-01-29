"""
Main orchestrator for Mémoire des Territoires.
Coordinates all agents and skills for scenario generation.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Union, List, Optional
from datetime import datetime

from utils.claude_client import ClaudeClient
from utils.logger import setup_logger, AgentLogger
from utils.skill_loader import SkillLoader

logger = logging.getLogger(__name__)


class ScenarioMakerOrchestrator:
    """
    Main orchestrator that coordinates all agents and skills.
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        api_key: Optional[str] = None,
        log_level: str = "INFO"
    ):
        """
        Initialize the orchestrator.
        
        Args:
            config_path: Path to configuration file (defaults to config/default_config.json)
            api_key: Anthropic API key (defaults to env variable)
            log_level: Logging level
        """
        # Setup logging
        log_file = os.getenv("LOG_FILE", "./logs/memoire_territoires.log")
        self.logger = setup_logger(
            name="memoire_territoires",
            level=log_level,
            log_file=log_file
        )
        
        logger.info("=" * 80)
        logger.info("Initializing Mémoire des Territoires Orchestrator")
        logger.info("=" * 80)
        
        # Initialize Claude client
        try:
            self.client = ClaudeClient(api_key=api_key)
            logger.info("Claude client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Claude client: {e}")
            raise
        
        # Load default configuration
        self.config_path = config_path or "config/default_config.json"
        self.default_config = self._load_config(self.config_path)
        logger.info(f"Loaded configuration from {self.config_path}")
        
        # Load agents and skills
        self.agents = {}
        self.skills = {}
        self._load_all_skills()
        
        logger.info("Orchestrator initialization complete")
        logger.info(f"Loaded {len(self.agents)} agents, {len(self.skills)} skills")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Config file not found: {config_path}, using empty config")
            return {}
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
    
    def _load_all_skills(self):
        """Load all agents and skills from their directories."""
        # Load agents
        agents_dir = Path("agents")
        if agents_dir.exists():
            logger.info("Loading agents...")
            self.agents = SkillLoader.load_all_skills(
                agents_dir,
                self.client.client,
                skill_type="agents"
            )
            logger.info(f"Loaded {len(self.agents)} agents: {list(self.agents.keys())}")
        else:
            logger.warning("Agents directory not found")
        
        # Load skills
        skills_dir = Path("skills")
        if skills_dir.exists():
            logger.info("Loading skills...")
            self.skills = SkillLoader.load_all_skills(
                skills_dir,
                self.client.client,
                skill_type="skills"
            )
            logger.info(f"Loaded {len(self.skills)} skills: {list(self.skills.keys())}")
        else:
            logger.warning("Skills directory not found")
    
    def create_scenarios(
        self,
        user_input: Union[str, Dict],
        mode: str = "simple",
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main pipeline to create scenarios - Full pipeline v2.
        
        Args:
            user_input: User prompt (str) or expert config (dict)
            mode: "simple" or "expert"
            output_dir: Directory to save outputs (defaults to ./output)
            
        Returns:
            Dict with generation results including scenarios and metadata
        """
        logger.info("=" * 80)
        logger.info(f"Starting FULL scenario generation pipeline (mode: {mode})")
        logger.info("=" * 80)
        
        start_time = datetime.now()
        
        try:
            # Step 1: Parse request with Agent 0
            config = self._run_agent_0(user_input, mode)
            
            # Get number of scenarios to generate
            num_scenarios = config.get('scenario_config', {}).get('generation_parameters', {}).get('nombre_scenarios', {}).get('value', 3)
            
            scenarios_complete = []
            
            # Generate each scenario
            for i in range(num_scenarios):
                logger.info(f"\n{'='*80}")
                logger.info(f"Generating scenario {i+1}/{num_scenarios}")
                logger.info(f"{'='*80}\n")
                
                try:
                    # Agent 1: Structure
                    structure = self._run_agent_1(config, i + 1)
                    
                    # Agent 2: Writing
                    scenario = self._run_agent_2(structure, config)
                    
                    # Agent 3: Production
                    timeline = self._run_agent_3(scenario, config)
                    
                    scenarios_complete.append({
                        'structure': structure,
                        'scenario': scenario,
                        'timeline': timeline
                    })
                    
                    logger.info(f"\n✓ Scenario {i+1} completed successfully")
                    
                except Exception as e:
                    logger.error(f"Error generating scenario {i+1}: {e}", exc_info=True)
                    scenarios_complete.append({
                        'error': str(e),
                        'scenario_id': i + 1
                    })
            
            # Build final result
            result = {
                'config': config,
                'scenarios': scenarios_complete,
                'generation_time': (datetime.now() - start_time).total_seconds(),
                'status': 'success',
                'message': f'Pipeline completed: {len(scenarios_complete)} scenarios generated'
            }
            
            # Save outputs
            if output_dir:
                self._save_complete_outputs(result, output_dir)
            
            logger.info("=" * 80)
            logger.info(f"FULL PIPELINE completed in {result['generation_time']:.2f}s")
            logger.info(f"Generated {len(scenarios_complete)} scenarios")
            logger.info("=" * 80)
            
            return result
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'generation_time': (datetime.now() - start_time).total_seconds()
            }
    
    def _run_agent_0(self, user_input: Union[str, Dict], mode: str) -> Dict:
        """Run Agent 0: Request Parser."""
        if 'agent_0_request_parser' not in self.agents:
            raise ValueError("Agent 0 not loaded")
        
        agent_0 = self.agents['agent_0_request_parser']['instance']
        agent_0_logger = AgentLogger("Agent 0")
        
        agent_0_logger.log_start("Parse request and build configuration")
        config = agent_0.parse(user_input, mode, self.default_config)
        agent_0_logger.log_end("Parse request", status="success")
        
        # Validate
        validation = agent_0.validate_configuration(config)
        if validation['warnings']:
            for warning in validation['warnings']:
                logger.warning(f"Config: {warning}")
        
        if not validation['valid']:
            raise ValueError(f"Configuration invalid: {validation['errors']}")
        
        return config
    
    def _run_agent_1(self, config: Dict, scenario_num: int) -> Dict:
        """Run Agent 1: Narrative Structure."""
        if 'agent_1_structure' not in self.agents:
            raise ValueError("Agent 1 not loaded")
        
        agent_1 = self.agents['agent_1_structure']['instance']
        agent_1_logger = AgentLogger("Agent 1")
        
        agent_1_logger.log_start(f"Create narrative structure #{scenario_num}")
        structure = agent_1.create_narrative_structure(config, scenario_num)
        agent_1_logger.log_end("Create structure", status="success")
        
        return structure
    
    def _run_agent_2(self, structure: Dict, config: Dict) -> Dict:
        """Run Agent 2: Scenario Writer."""
        if 'agent_2_writing' not in self.agents:
            raise ValueError("Agent 2 not loaded")
        
        agent_2 = self.agents['agent_2_writing']['instance']
        
        # Inject skills
        agent_2.set_skills(self.skills)
        
        agent_2_logger = AgentLogger("Agent 2")
        
        agent_2_logger.log_start("Write complete scenario")
        scenario = agent_2.write_complete_scenario(structure, config)
        agent_2_logger.log_end("Write scenario", status="success")
        
        return scenario
    
    def _run_agent_3(self, scenario: Dict, config: Dict) -> Dict:
        """Run Agent 3: Production Engineer."""
        if 'agent_3_production' not in self.agents:
            raise ValueError("Agent 3 not loaded")
        
        agent_3 = self.agents['agent_3_production']['instance']
        
        # Inject skills
        agent_3.set_skills(self.skills)
        
        agent_3_logger = AgentLogger("Agent 3")
        
        agent_3_logger.log_start("Create audio timeline")
        timeline = agent_3.create_audio_timeline(scenario, None, config)
        agent_3_logger.log_end("Create timeline", status="success")
        
        return timeline
    
    def _save_complete_outputs(self, result: Dict, output_dir: str):
        """Save all outputs to directory."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save config
        config_file = output_path / "scenarios" / f"config_{timestamp}.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(result['config'], f, indent=2, ensure_ascii=False)
        
        # Save each scenario and timeline
        for i, scenario_data in enumerate(result.get('scenarios', [])):
            if 'error' in scenario_data:
                continue
            
            # Save scenario
            scenario_file = output_path / "scenarios" / f"scenario_{i+1}_{timestamp}.json"
            with open(scenario_file, 'w', encoding='utf-8') as f:
                json.dump(scenario_data['scenario'], f, indent=2, ensure_ascii=False)
            
            # Save timeline
            timeline_file = output_path / "timelines" / f"timeline_{i+1}_{timestamp}.json"
            timeline_file.parent.mkdir(parents=True, exist_ok=True)
            with open(timeline_file, 'w', encoding='utf-8') as f:
                json.dump(scenario_data['timeline'], f, indent=2, ensure_ascii=False)
        
        logger.info(f"All outputs saved to {output_dir}")
    
    def _save_output(self, result: Dict, output_dir: str):
        """Save generation results to output directory."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_path / f"config_{timestamp}.json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info(f"Output saved to {output_file}")
        except Exception as e:
            logger.error(f"Error saving output: {e}")
    
    def list_available_skills(self) -> Dict[str, List[str]]:
        """List all available agents and skills."""
        return {
            'agents': list(self.agents.keys()),
            'skills': list(self.skills.keys())
        }
    
    def get_skill_info(self, skill_name: str) -> Optional[Dict]:
        """Get detailed information about a skill."""
        if skill_name in self.agents:
            return self.agents[skill_name]['config']
        elif skill_name in self.skills:
            return self.skills[skill_name]['config']
        return None
