"""
Agent 0: Request Parser & Config Builder
Parses user requests and builds complete scenario configuration.
"""

import json
import logging
from typing import Dict, Any, Union, Tuple, List
from copy import deepcopy

logger = logging.getLogger(__name__)


class RequestParserAgent:
    """Agent 0: Parses requests and builds scenario configuration."""
    
    def __init__(self, client):
        """
        Initialize the request parser agent.
        
        Args:
            client: Claude client instance
        """
        self.client = client
        self.model = "claude-sonnet-4-5"
        self.temperature = 0.1
        self.max_tokens = 6000
        
        self.system_prompt = """Vous êtes un expert en analyse de besoins pour la création de contenus audio historiques. Votre rôle est d'extraire avec précision tous les paramètres nécessaires depuis une demande utilisateur.

Règles strictes :
1. Extrayez UNIQUEMENT les informations explicitement mentionnées ou fortement impliquées
2. Marquez clairement ce qui est spécifié par l'utilisateur vs valeur par défaut
3. Assurez la cohérence : ajustez automatiquement les incompatibilités
4. Retournez TOUJOURS un JSON valide et complet
5. Soyez précis sur les dates, durées, lieux et thématiques historiques"""
        
        logger.info("RequestParserAgent initialized")
    
    def parse(
        self,
        user_input: Union[str, Dict],
        mode: str,
        default_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Main parse method that routes to simple or expert mode.
        
        Args:
            user_input: User prompt (str) or expert config (dict)
            mode: "simple" or "expert"
            default_config: Default configuration to merge with
            
        Returns:
            Complete scenario configuration
        """
        logger.info(f"Parsing request in {mode} mode")
        
        if mode == "simple":
            return self.parse_simple_prompt(str(user_input), default_config)
        elif mode == "expert":
            return self.merge_expert_config(dict(user_input), default_config)
        else:
            raise ValueError(f"Unknown mode: {mode}")
    
    def parse_simple_prompt(self, user_prompt: str, default_config: Dict) -> Dict:
        """
        Parse a simple natural language prompt.
        
        Args:
            user_prompt: Natural language request
            default_config: Default configuration
            
        Returns:
            Extracted configuration
        """
        logger.info(f"Parsing simple prompt: {user_prompt[:100]}...")
        
        # Prepare prompt for Claude
        prompt = f"""Analysez cette demande et extrayez TOUS les paramètres pour générer des archives audio historiques.

DEMANDE UTILISATEUR :
{user_prompt}

CONFIGURATION PAR DÉFAUT (référence) :
{json.dumps(default_config.get('scenario_config', {}).get('generation_parameters', {}), indent=2, ensure_ascii=False)}

INSTRUCTIONS :
1. Identifiez la forme narrative (documentaire, conte, interview, etc.)
2. Extrayez la durée (convertissez en secondes)
3. Déterminez le ton approprié
4. Identifiez le public cible
5. Extrayez période historique, lieux, thématiques
6. Pour chaque paramètre extrait, marquez user_specified: true
7. Pour les paramètres non mentionnés, utilisez les valeurs par défaut avec user_specified: false

Retournez un JSON avec cette structure :
{{
  "generation_parameters": {{
    "forme": {{"value": "...", "user_specified": true/false}},
    "duree": {{"value": 120, "user_specified": true/false}},
    "ton": {{"value": "...", "user_specified": true/false}},
    "public_cible": {{"value": "...", "user_specified": true/false}},
    ...
  }},
  "historical_context": {{
    "period": {{"start_year": ..., "end_year": ...}},
    "location": {{"primary": "...", "specific_areas": [...]}},
    "themes": {{"primary": [...], "secondary": [...]}}
  }}
}}

JSON :"""
        
        try:
            response = self.client.create_message(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                system=self.system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Extract JSON from response
            response_text = response.content[0].text
            
            # Try to parse JSON
            extracted = self._extract_json(response_text)
            
            # Merge with default config
            config = self._merge_configs(extracted, default_config)
            
            # Validate and adjust
            config = self._validate_and_adjust(config)
            
            logger.info("Simple prompt parsed successfully")
            return config
            
        except Exception as e:
            logger.error(f"Error parsing simple prompt: {e}", exc_info=True)
            # Fallback to default config
            logger.warning("Falling back to default configuration")
            return deepcopy(default_config)
    
    def merge_expert_config(
        self,
        user_config: Dict,
        default_config: Dict
    ) -> Dict:
        """
        Merge expert configuration with defaults.
        
        Args:
            user_config: User-provided configuration
            default_config: Default configuration
            
        Returns:
            Merged configuration
        """
        logger.info("Merging expert configuration")
        
        config = deepcopy(default_config)
        
        # Deep merge user config into default
        config = self._deep_merge(config, user_config)
        
        # Mark all provided fields as user_specified
        self._mark_user_specified(config, user_config)
        
        # Validate
        config = self._validate_and_adjust(config)
        
        logger.info("Expert config merged successfully")
        return config
    
    def validate_configuration(self, config: Dict) -> Dict[str, Any]:
        """
        Validate configuration and return errors/warnings.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []
        
        gen_params = config.get('scenario_config', {}).get('generation_parameters', {})
        
        # Check duration
        duree = gen_params.get('duree', {}).get('value', 120)
        if duree < 60:
            warnings.append(f"Durée très courte: {duree}s. Recommandé: 120s minimum")
        elif duree > 600:
            warnings.append(f"Durée très longue: {duree}s. Considérez diviser en épisodes")
        
        # Check tone/audience consistency
        public = gen_params.get('public_cible', {}).get('value', '')
        ton = gen_params.get('ton', {}).get('value', '')
        
        if public in ['enfants', 'scolaire_primaire']:
            if ton in ['dramatique_immersif', 'emotionnel_personnel']:
                warnings.append(
                    f"Ton '{ton}' peut être trop intense pour '{public}'. "
                    "Considérez 'pedagogique_accessible'"
                )
        
        # Check balance
        balance = gen_params.get('equilibre_narration_archives', {}).get('value', 0.6)
        if balance < 0.3:
            warnings.append("Équilibre faible peut résulter en trop d'archives")
        elif balance > 0.9:
            warnings.append("Équilibre élevé peut sous-utiliser les archives")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def generate_summary(self, config: Dict) -> str:
        """
        Generate human-readable summary of configuration.
        
        Args:
            config: Configuration to summarize
            
        Returns:
            Formatted summary string
        """
        gen_params = config.get('scenario_config', {}).get('generation_parameters', {})
        hist_context = config.get('scenario_config', {}).get('historical_context', {})
        
        summary_parts = ["=== Configuration Générée ===\n"]
        
        # Main parameters
        summary_parts.append("Paramètres principaux:")
        summary_parts.append(f"  - Forme: {gen_params.get('forme', {}).get('value', 'N/A')}")
        summary_parts.append(f"  - Durée: {gen_params.get('duree', {}).get('value', 'N/A')}s")
        summary_parts.append(f"  - Ton: {gen_params.get('ton', {}).get('value', 'N/A')}")
        summary_parts.append(f"  - Public: {gen_params.get('public_cible', {}).get('value', 'N/A')}")
        summary_parts.append(f"  - Scénarios: {gen_params.get('nombre_scenarios', {}).get('value', 3)}")
        
        # Historical context
        period = hist_context.get('period', {})
        if period.get('start_year'):
            summary_parts.append(f"\nContexte historique:")
            summary_parts.append(f"  - Période: {period.get('start_year')}-{period.get('end_year')}")
            
            location = hist_context.get('location', {})
            if location.get('primary'):
                summary_parts.append(f"  - Lieu: {location.get('primary')}")
            
            themes = hist_context.get('themes', {})
            if themes.get('primary'):
                summary_parts.append(f"  - Thèmes: {', '.join(themes.get('primary', []))}")
        
        # User-specified fields
        user_specified = []
        for key, value in gen_params.items():
            if isinstance(value, dict) and value.get('user_specified'):
                user_specified.append(key)
        
        if user_specified:
            summary_parts.append(f"\nParamètres spécifiés par l'utilisateur: {', '.join(user_specified)}")
        
        return "\n".join(summary_parts)
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from Claude response."""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract from markdown code block
        import re
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON object
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError("Could not extract valid JSON from response")
    
    def _merge_configs(self, extracted: Dict, default: Dict) -> Dict:
        """Merge extracted config into default."""
        result = deepcopy(default)
        return self._deep_merge(result, {'scenario_config': extracted})
    
    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """Deep merge two dictionaries."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
    
    def _mark_user_specified(self, config: Dict, user_config: Dict, prefix: str = ''):
        """Recursively mark user-specified fields."""
        for key, value in user_config.items():
            if isinstance(value, dict):
                if 'value' in value:
                    # This is a parameter dict
                    if key in config:
                        config[key]['user_specified'] = True
                else:
                    # Recurse
                    if key in config:
                        self._mark_user_specified(config[key], value, f"{prefix}.{key}")
    
    def _validate_and_adjust(self, config: Dict) -> Dict:
        """Validate and adjust configuration for consistency."""
        gen_params = config.get('scenario_config', {}).get('generation_parameters', {})
        
        # Auto-adjust tone for children
        public = gen_params.get('public_cible', {}).get('value')
        ton = gen_params.get('ton', {}).get('value')
        
        if public in ['enfants', 'scolaire_primaire']:
            if ton in ['dramatique_immersif', 'emotionnel_personnel']:
                logger.info(f"Auto-adjusting tone from '{ton}' to 'pedagogique_accessible' for children")
                gen_params['ton']['value'] = 'pedagogique_accessible'
                gen_params['ton']['user_specified'] = False  # This was auto-adjusted
        
        return config
    
    def _generate_axe_distribution(self, nombre_scenarios: int) -> Dict[str, str]:
        """Generate distribution of narrative axes for mixed mode."""
        axes = ['travailleur', 'objet_lieu', 'evenement_historique', 'contexte_social']
        distribution = {}
        
        for i in range(nombre_scenarios):
            distribution[f'scenario_{i+1}'] = axes[i % len(axes)]
        
        return distribution
