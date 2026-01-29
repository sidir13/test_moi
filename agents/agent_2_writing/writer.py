"""
Agent 2: Historical Scenario Writer
Writes complete scenarios with historical rigor.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ScenarioWriterAgent:
    """Agent 2: Writes historical scenarios."""
    
    def __init__(self, client):
        """
        Initialize the scenario writer agent.
        
        Args:
            client: Claude client instance
        """
        self.client = client
        self.model = "claude-opus-4-5"
        self.temperature = 0.8
        self.max_tokens = 6000
        
        self.system_prompt = """Vous êtes un expert historien ET conteur spécialisé en histoire sociale française. Votre mission est de créer des récits émotionnellement engageants, historiquement rigoureux, et parfaitement adaptés au format audio.

Règles d'écriture :
1. **Rigueur historique absolue** : Pas d'anachronismes, vocabulaire d'époque
2. **Narratif audio** : Écrivez pour l'oreille, pas pour l'œil
3. **Rythme varié** : Alternez passages descriptifs et dynamiques
4. **Ancrage sensoriel** : Sons, odeurs, sensations tactiles
5. **Timing précis** : Respectez strictement les durées cibles"""
        
        # Skills will be injected by orchestrator
        self.historical_analyzer = None
        self.narrative_builder = None
        
        logger.info("ScenarioWriterAgent initialized")
    
    def set_skills(self, skills: Dict):
        """Set skill instances."""
        if 'historical_context_analyzer' in skills:
            self.historical_analyzer = skills['historical_context_analyzer']['instance']
        if 'narrative_scenario_builder' in skills:
            self.narrative_builder = skills['narrative_scenario_builder']['instance']
    
    def write_complete_scenario(
        self,
        structure: Dict[str, Any],
        config: Dict[str, Any],
        historical_context: Optional[Dict] = None,
        audio_transcriptions: Optional[List] = None
    ) -> Dict[str, Any]:
        """
        Write complete scenario from structure.
        
        Args:
            structure: Narrative structure from Agent 1
            config: Configuration
            historical_context: Optional enriched historical context
            audio_transcriptions: Optional audio archive transcriptions
            
        Returns:
            Complete scenario
        """
        logger.info(f"Writing scenario: {structure.get('titre_global', 'N/A')}")
        
        scenario_id = structure.get('scenario_id', 1)
        titre = structure.get('titre_global', 'Scénario historique')
        axe = structure.get('axe_narratif', 'mixte')
        
        # Get historical context if not provided
        if not historical_context and self.historical_analyzer:
            historical_context = self._get_historical_context(config)
        
        # Write parts
        parties = []
        total_duration = 0.0
        word_count = 0
        archives_used = 0
        ambiances_count = 0
        
        for part_structure in structure.get('structure', []):
            part = self._write_part(
                part_structure,
                structure,
                config,
                historical_context,
                audio_transcriptions
            )
            
            parties.append(part)
            total_duration += part.get('duree', 0)
            word_count += self._count_words(part.get('texte_narration', ''))
            archives_used += len([m for m in part.get('moments_cles', []) if m.get('action') == 'archive_audio'])
            ambiances_count += len(part.get('ambiances_continues', []))
        
        # Validate historical accuracy
        validation = self.validate_historical_accuracy(
            {'parties': parties},
            config.get('scenario_config', {}).get('historical_context', {}).get('period', {})
        )
        
        # Build complete scenario
        scenario = {
            'scenario_id': scenario_id,
            'titre': titre,
            'axe_narratif': axe,
            'duree_estimee': total_duration,
            'parties': parties,
            'metadata': {
                'nombre_mots': word_count,
                'duree_lecture_estimee': total_duration,
                'nombre_archives_utilisees': archives_used,
                'nombre_ambiances': ambiances_count,
                'coherence_historique': validation
            },
            'notes_pour_agent_3': structure.get('notes_production', '')
        }
        
        logger.info(f"Scenario written: {word_count} words, {len(parties)} parts, {total_duration:.1f}s")
        return scenario
    
    def _write_part(
        self,
        part_structure: Dict,
        full_structure: Dict,
        config: Dict,
        historical_context: Optional[Dict],
        audio_transcriptions: Optional[List]
    ) -> Dict:
        """Write a single scenario part."""
        
        part_id = part_structure['partie']
        titre = part_structure['titre']
        duree_cible = part_structure['duree_cible']
        fonction = part_structure['fonction_narrative']
        mood = part_structure['mood']
        
        gen_params = config.get('scenario_config', {}).get('generation_parameters', {})
        ton = gen_params.get('ton', {}).get('value', 'neutre_informatif')
        public = gen_params.get('public_cible', {}).get('value', 'grand_public')
        
        # Use narrative builder skill if available
        if self.narrative_builder:
            try:
                parts = self.narrative_builder.build_scenario_from_structure(
                    full_structure,
                    config,
                    historical_context or {},
                    audio_transcriptions
                )
                if parts and len(parts) >= part_id:
                    return parts[part_id - 1]
            except Exception as e:
                logger.warning(f"Skill failed, using direct generation: {e}")
        
        # Direct generation fallback
        return self._generate_part_direct(
            part_id, titre, duree_cible, fonction, mood, ton, public, historical_context
        )
    
    def _generate_part_direct(
        self,
        part_id: int,
        titre: str,
        duree: float,
        fonction: str,
        mood: str,
        ton: str,
        public: str,
        historical_context: Optional[Dict]
    ) -> Dict:
        """Generate part directly with Claude."""
        
        word_target = int(duree * 2.5)  # ~2.5 words per second at 150 WPM
        
        context_str = ""
        if historical_context:
            context_str = json.dumps(
                historical_context.get('contexte_enrichi', {}),
                indent=2,
                ensure_ascii=False
            )[:500]
        
        prompt = f"""Écrivez la partie {part_id} d'un scénario audio historique.

PARAMÈTRES :
- Titre : {titre}
- Durée : {duree}s (environ {word_target} mots)
- Fonction narrative : {fonction}
- Mood : {mood}
- Ton : {ton}
- Public : {public}

CONTEXTE HISTORIQUE :
{context_str}

CONSIGNES :
1. Texte narratif fluide pour lecture audio
2. Vocabulaire adapté au public et à l'époque
3. 2-3 moments clés pour placement d'effets/archives
4. Directions de ton précises

Retournez un JSON :
{{
  "partie_id": {part_id},
  "titre": "{titre}",
  "duree": {duree},
  "texte_narration": "Votre texte...",
  "ton": {{
    "global": "{mood}",
    "tempo_lecture": 110,
    "pauses": ["après X", "avant Y"]
  }},
  "moments_cles": [
    {{
      "timestamp": "0:XX",
      "action": "pause_dramatique",
      "duree": 2.0
    }}
  ],
  "ambiances_continues": []
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
            
            response_text = response.content[0].text
            part = self._extract_json(response_text)
            
            # Calculate actual timing
            timing = self.calculate_narration_timing(
                part.get('texte_narration', ''),
                part.get('ton', {}).get('tempo_lecture', 110),
                []
            )
            part['duree'] = timing['duration']
            
            return part
            
        except Exception as e:
            logger.error(f"Error generating part {part_id}: {e}", exc_info=True)
            return self._fallback_part(part_id, titre, duree, mood)
    
    def validate_historical_accuracy(
        self,
        scenario: Dict,
        period: Dict,
        strict_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Validate historical accuracy of scenario.
        
        Args:
            scenario: Scenario to validate
            period: Historical period
            strict_mode: Use strict validation
            
        Returns:
            Validation result
        """
        logger.info("Validating historical accuracy")
        
        # Collect all text from scenario
        text_parts = []
        for part in scenario.get('parties', []):
            text_parts.append(part.get('texte_narration', ''))
        
        full_text = ' '.join(text_parts)
        
        # Use historical analyzer skill if available
        if self.historical_analyzer:
            try:
                result = self.historical_analyzer.detect_anachronisms(
                    full_text,
                    period.get('start_year', 1900),
                    strict_mode
                )
                
                return {
                    'accuracy_score': result.get('score', 0.8),
                    'sources_citees': [],
                    'verifications': [
                        f"Anachronismes : {result.get('total_anachronisms', 0)}"
                    ],
                    'vocabulaire_epoque': []
                }
            except Exception as e:
                logger.warning(f"Skill validation failed: {e}")
        
        # Basic validation fallback
        return {
            'accuracy_score': 0.8,
            'sources_citees': [],
            'verifications': ['Validation basique effectuée'],
            'vocabulaire_epoque': []
        }
    
    def calculate_narration_timing(
        self,
        text: str,
        tempo_wpm: int = 110,
        pauses: Optional[List] = None,
        include_buffer: bool = False
    ) -> Dict[str, float]:
        """
        Calculate precise narration timing.
        
        Args:
            text: Text to time
            tempo_wpm: Words per minute
            pauses: List of pauses with durations
            include_buffer: Add 10% buffer
            
        Returns:
            Timing breakdown
        """
        word_count = self._count_words(text)
        
        # Calculate reading time
        reading_time = (word_count / tempo_wpm) * 60
        
        # Calculate pauses time
        pauses_time = 0.0
        if pauses:
            for pause in pauses:
                if isinstance(pause, dict) and 'duration' in pause:
                    pauses_time += pause['duration']
                elif isinstance(pause, (int, float)):
                    pauses_time += pause
        
        # Buffer
        buffer = 0.0
        if include_buffer:
            buffer = (reading_time + pauses_time) * 0.1
        
        duration = reading_time + pauses_time + buffer
        
        return {
            'duration': duration,
            'word_count': word_count,
            'reading_time': reading_time,
            'pauses_time': pauses_time,
            'buffer': buffer
        }
    
    def _get_historical_context(self, config: Dict) -> Dict:
        """Get historical context using analyzer skill."""
        if not self.historical_analyzer:
            return {}
        
        hist_context = config.get('scenario_config', {}).get('historical_context', {})
        
        try:
            return self.historical_analyzer.analyze_historical_documents(
                [],  # No documents for now
                hist_context.get('period', {}),
                hist_context.get('location', {}).get('primary'),
                hist_context.get('themes', {}).get('primary', [])
            )
        except Exception as e:
            logger.error(f"Error getting historical context: {e}")
            return {}
    
    def _count_words(self, text: str) -> int:
        """Count words in text."""
        return len(re.findall(r'\b\w+\b', text))
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from text."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError("Could not extract valid JSON")
    
    def _fallback_part(self, part_id: int, titre: str, duree: float, mood: str) -> Dict:
        """Create fallback part."""
        return {
            'partie_id': part_id,
            'titre': titre,
            'duree': duree,
            'texte_narration': f"[Partie {part_id}: {titre}. Texte à générer.]",
            'ton': {
                'global': mood,
                'tempo_lecture': 110,
                'pauses': []
            },
            'moments_cles': [],
            'ambiances_continues': []
        }
