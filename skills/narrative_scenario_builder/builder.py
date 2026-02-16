"""
Narrative Scenario Builder Skill
Builds narrative scenarios from structures.
"""

import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class NarrativeScenarioBuilder:
    """Builds narrative scenarios from structures."""
    
    def __init__(self, client):
        """
        Initialize the builder.
        
        Args:
            client: Claude client instance
        """
        self.client = client
        self.model = "claude-opus-4-5"
        self.temperature = 0.8
        self.max_tokens = 6000
        
        logger.info("NarrativeScenarioBuilder initialized")
    
    def build_scenario_from_structure(
        self,
        structure: Dict[str, Any],
        config: Dict[str, Any],
        historical_context: Dict[str, Any],
        audio_transcriptions: Optional[List] = None
    ) -> List[Dict]:
        """
        Build complete scenario from narrative structure.
        
        Args:
            structure: Narrative structure from Agent 1
            config: Full configuration
            historical_context: Enriched historical context
            audio_transcriptions: Available audio archive transcriptions
            
        Returns:
            List of scenario parts
        """
        logger.info(f"Building scenario: {structure.get('titre_global', 'N/A')}")
        
        parts = []
        gen_params = config.get('scenario_config', {}).get('generation_parameters', {})
        original_prompt = config.get('scenario_config', {}).get('user_input', {}).get('original_prompt', '')
        angle = gen_params.get('angle_scenarisation', {}).get('value', 'auto')
        
        for part_structure in structure.get('structure', []):
            part = self._build_part(
                part_structure,
                structure,
                gen_params,
                historical_context,
                audio_transcriptions,
                angle_scenarisation=angle,
                original_prompt=original_prompt
            )
            parts.append(part)
        
        logger.info(f"Built {len(parts)} scenario parts")
        return parts
    
    def _build_part(
        self,
        part_structure: Dict,
        full_structure: Dict,
        gen_params: Dict,
        historical_context: Dict,
        audio_transcriptions: Optional[List],
        angle_scenarisation: str = "auto",
        original_prompt: str = ""
    ) -> Dict:
        """Build a single scenario part."""
        
        part_num = part_structure['partie']
        titre = part_structure['titre']
        duree = part_structure['duree_cible']
        fonction = part_structure['fonction_narrative']
        mood = part_structure['mood']
        elements = part_structure['elements_necessaires']
        
        ton = gen_params.get('ton', {}).get('value', 'neutre_informatif')
        public = gen_params.get('public_cible', {}).get('value', 'grand_public')

        # Build audio transcriptions section for the prompt
        transcriptions_section = ""
        if audio_transcriptions:
            transcriptions_lines = []
            for t in audio_transcriptions:
                name = t.get("file_name", "audio")
                text = t.get("transcription", "")
                if text:
                    transcriptions_lines.append(f"--- {name} ---\n{text[:3000]}")
            if transcriptions_lines:
                transcriptions_section = (
                    "\n\nTRANSCRIPTIONS AUDIO DISPONIBLES (témoignages réels à intégrer) :\n"
                    + "\n\n".join(transcriptions_lines)
                )

        # Build original prompt section
        prompt_section = ""
        if original_prompt and original_prompt.strip():
            prompt_section = f"\nDEMANDE ORIGINALE : \"{original_prompt.strip()}\""

        # Build prompt for narrative generation
        prompt = f"""Écrivez la partie {part_num} d'un scénario audio historique.

STRUCTURE DE CETTE PARTIE :
- Titre : {titre}
- Durée cible : {duree}s
- Fonction narrative : {fonction}
- Mood : {mood}
- Éléments nécessaires : {', '.join(elements)}

CONTEXTE GLOBAL :
- Titre du scénario : {full_structure.get('titre_global')}
- Axe narratif : {full_structure.get('axe_narratif')}
- Arc émotionnel : {full_structure.get('arc_emotionnel_global')}
- Angle de scénarisation : {angle_scenarisation}

PARAMÈTRES :
- Ton : {ton}
- Public : {public}
{prompt_section}

CONTEXTE HISTORIQUE (SEULE source de faits autorisée) :
{json.dumps(historical_context.get('contexte_enrichi', {}), indent=2, ensure_ascii=False)[:4000]}
{transcriptions_section}

CONSIGNES D'ÉCRITURE :
1. Écrivez un texte narratif CONTINU et immersif pour {duree}s de lecture (environ {int(duree * 2.5)} mots)
2. Suivez fidèlement l'angle de scénarisation ci-dessus
3. Adaptez le vocabulaire au public cible et à l'époque
4. Respectez le mood et la fonction narrative
5. 2-3 moments clés pour placement d'archives ou effets sonores + directions de ton
6. Si des transcriptions audio sont fournies, UTILISEZ-LES comme source primaire
7. Assurez la CONTINUITÉ avec les sections précédentes et suivantes

GARDE-FOU ANTI-HALLUCINATION :
- Basez-vous EXCLUSIVEMENT sur le contexte historique et les transcriptions ci-dessus.
- N'inventez AUCUN nom, date, lieu ou événement non mentionné dans les sources.
- Si le contexte manque, utilisez des formulations vagues : "un homme", "certains ouvriers", "dans ces années-là..." etc.
- Les atmosphères, émotions et descriptions sensorielles peuvent être librement créées, mais PAS les faits historiques.

Retournez un JSON avec cette structure :
{{
  "partie_id": {part_num},
  "titre": "{titre}",
  "duree": {duree},
  "texte_narration": "Le texte narratif complet...",
  "ton": {{
    "global": "{mood}",
    "tempo_lecture": 110,
    "pauses": ["position des pauses"],
    "intonation": "description"
  }},
  "moments_cles": [
    {{
      "timestamp": "0:15",
      "action": "pause_dramatique",
      "duree": 2.0,
      "consigne": "Silence pour laisser résonner"
    }}
  ]
}}

JSON :"""
        
        try:
            response = self.client.create_message(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            response_text = response.content[0].text
            part = self._extract_json(response_text)
            
            logger.info(f"Part {part_num} built: {len(part.get('texte_narration', ''))} chars")
            return part
            
        except Exception as e:
            logger.error(f"Error building part {part_num}: {e}", exc_info=True)
            return self._fallback_part(part_num, titre, duree, mood)
    
    def adapt_vocabulary_to_audience(
        self,
        text: str,
        audience: str,
        historical_authenticity: float = 0.7
    ) -> str:
        """
        Adapt vocabulary to target audience.
        
        Args:
            text: Original text
            audience: Target audience
            historical_authenticity: 0.0 (modern) to 1.0 (authentic)
            
        Returns:
            Adapted text
        """
        logger.info(f"Adapting text to audience: {audience}")
        
        if audience in ['enfants', 'scolaire_primaire']:
            return self._simplify_for_children(text)
        elif audience == 'specialiste':
            return text  # Keep as is
        else:
            return self._balance_accessibility(text, historical_authenticity)
    
    def generate_dramatic_moment(
        self,
        context: str,
        emotion_target: str,
        duration: float,
        tone: str
    ) -> str:
        """
        Generate a dramatic key moment.
        
        Args:
            context: Context for the moment
            emotion_target: Target emotion
            duration: Duration in seconds
            tone: Tone type
            
        Returns:
            Narrative description
        """
        logger.info(f"Generating dramatic moment: {emotion_target}")
        
        word_count = int(duration * 2.5)
        
        prompt = f"""Créez un moment dramatique pour un récit audio historique.

CONTEXTE : {context}
ÉMOTION CIBLE : {emotion_target}
DURÉE : {duration}s (environ {word_count} mots)
TON : {tone}

Écrivez un passage narratif court et intense qui crée cette émotion.
Utilisez des descriptions sensorielles et un rythme adapté au format audio.

Texte :"""
        
        try:
            response = self.client.create_message(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=500
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            logger.error(f"Error generating dramatic moment: {e}")
            return f"[Moment dramatique : {emotion_target}]"
    
    def create_immersive_description(
        self,
        subject: str,
        senses: List[str],
        mood: str,
        period: int,
        max_words: int = 50
    ) -> str:
        """
        Create immersive sensory description.
        
        Args:
            subject: What to describe
            senses: Which senses to engage
            mood: Mood of description
            period: Historical period
            max_words: Maximum word count
            
        Returns:
            Immersive description
        """
        logger.info(f"Creating immersive description: {subject}")
        
        senses_str = ', '.join(senses)
        
        prompt = f"""Créez une description immersive et sensorielle.

SUJET : {subject}
SENS À ENGAGER : {senses_str}
MOOD : {mood}
PÉRIODE : {period}
LONGUEUR : {max_words} mots maximum

Créez une description riche en détails sensoriels, adaptée à l'époque et au mood.
Format audio : privilégiez ce qui peut être évoqué à l'oreille.

Description :"""
        
        try:
            response = self.client.create_message(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=300
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            logger.error(f"Error creating description: {e}")
            return f"{subject} dans l'atmosphère de l'époque."
    
    def _simplify_for_children(self, text: str) -> str:
        """Simplify text for children."""
        # Basic simplification (in real system would be more sophisticated)
        replacements = {
            'portefaix': 'travailleurs du port',
            'débardeur': 'travailleurs',
            'palans': 'cordes et poulies',
            'barrique': 'gros tonneau',
            'cale': 'fond du bateau',
            'manœuvrer': 'utiliser',
            'hisser': 'monter'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text
    
    def _balance_accessibility(self, text: str, authenticity: float) -> str:
        """Balance between authenticity and accessibility."""
        if authenticity > 0.8:
            return text  # Keep authentic
        elif authenticity < 0.5:
            return self._simplify_for_children(text)
        else:
            # Add parenthetical explanations for technical terms
            # (simplified implementation)
            return text
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from text."""
        import re
        
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
    
    def _fallback_part(
        self,
        part_id: int,
        titre: str,
        duree: float,
        mood: str
    ) -> Dict:
        """Create fallback part if generation fails."""
        logger.warning(f"Creating fallback for part {part_id}")
        
        return {
            'partie_id': part_id,
            'titre': titre,
            'duree': duree,
            'texte_narration': f"[Partie {part_id} : {titre}. Texte à générer.]",
            'ton': {
                'global': mood,
                'tempo_lecture': 110,
                'pauses': [],
                'intonation': 'neutre'
            },
            'moments_cles': []
        }
