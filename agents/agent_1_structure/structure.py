"""
Agent 1: Narrative Structure Architect
Creates narrative structures for scenarios.
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class StructureArchitectAgent:
    """Agent 1: Creates narrative structure architecture."""
    
    def __init__(self, client):
        """
        Initialize the structure architect agent.
        
        Args:
            client: Claude client instance
        """
        self.client = client
        self.model = "claude-sonnet-4-5"
        self.temperature = 0.7
        self.max_tokens = 3000
        
        self.system_prompt = """Vous êtes un architecte narratif spécialisé en récits audio historiques. Votre expertise est la construction de structures narratives solides, émotionnellement engageantes et adaptées au format audio.

Principes de conception :
1. **Cohérence temporelle** : Respectez strictement la durée totale cible
2. **Arc émotionnel** : Créez une progression émotionnelle claire
3. **Rythme audio** : Variez intensité et tempo pour maintenir l'attention
4. **Fluidité narrative** : Le récit doit couler naturellement, sans ruptures artificielles entre sections. Privilégiez le liant et la continuité plutôt qu'un découpage rigide.
5. **Adaptation au public** : Ajustez complexité selon l'audience
6. **Liberté structurelle** : Vous décidez librement du nombre de sections (1 à 7) selon ce qui est naturel pour le récit. Un récit court peut n'avoir qu'une seule section continue.

RÈGLE ABSOLUE — RIGUEUR HISTORIQUE :
- Basez vos titres de sections et éléments narratifs UNIQUEMENT sur le contexte historique fourni ci-dessous.
- N'INVENTEZ JAMAIS de dates, noms de personnes, lieux ou événements historiques précis.
- Si le contexte est insuffisant, utilisez des formulations volontairement vagues : "un travailleur", "dans les années...", "sur les quais..." plutôt que d'inventer des détails.
- Les éléments narratifs (atmosphères, émotions, sensations) peuvent être créatifs, mais les FAITS doivent être traçables aux sources fournies."""
        
        logger.info("StructureArchitectAgent initialized")
    
    def create_narrative_structure(
        self,
        config: Dict[str, Any],
        scenario_num: int,
        audio_metadata: Optional[List] = None
    ) -> Dict[str, Any]:
        """
        Create complete narrative structure for a scenario.
        
        Args:
            config: Scenario configuration
            scenario_num: Scenario number (1, 2, 3...)
            audio_metadata: Optional metadata about available audio archives
            
        Returns:
            Narrative structure dict
        """
        logger.info(f"Creating narrative structure for scenario {scenario_num}")
        
        # Extract parameters from config
        gen_params = config.get('scenario_config', {}).get('generation_parameters', {})
        hist_context = config.get('scenario_config', {}).get('historical_context', {})
        
        duree = gen_params.get('duree', {}).get('value', 120)
        forme = gen_params.get('forme', {}).get('value', 'documentaire')
        ton = gen_params.get('ton', {}).get('value', 'neutre_informatif')
        public = gen_params.get('public_cible', {}).get('value', 'grand_public')
        axe = gen_params.get('axe_narratif', {}).get('value', 'mixte')
        structure_type = gen_params.get('structure_narrative', {}).get('value', 'chronologique')
        rythme = gen_params.get('rythme', {}).get('value', 'modere')
        angle_scenarisation = gen_params.get('angle_scenarisation', {}).get('value', 'auto')
        
        # Read original user prompt for context fidelity
        original_prompt = config.get('scenario_config', {}).get('user_input', {}).get('original_prompt', '')
        
        # Get specific axis for this scenario if mixed
        if axe == 'mixte':
            distribution = gen_params.get('axe_narratif', {}).get('distribution', {})
            axe = distribution.get(f'scenario_{scenario_num}', 'travailleur')
        
        # Define emotional arc
        emotional_arc = self.define_emotional_arc(
            ton, structure_type, duree, public
        )
        
        # Build audio metadata section
        audio_section = ""
        if audio_metadata:
            audio_lines = []
            for t in audio_metadata:
                name = t.get("file_name", "audio")
                text = t.get("transcription", "")
                if text:
                    audio_lines.append(f"- {name}: {text[:300]}...")
            if audio_lines:
                audio_section = "\n\nARCHIVES AUDIO DISPONIBLES :\n" + "\n".join(audio_lines)
        
        # Build angle description for prompt
        angle_descriptions = {
            "temoignage_croise": "Récit à la 1ère personne avec plusieurs témoins qui se relaient. Chaque voix apporte un regard différent sur le même vécu.",
            "chronique_sociale": "Chronique à la 3ème personne racontant la vie d'un groupe social, ses habitudes, son quotidien, ses luttes.",
            "journee_type": "Une journée type racontée du matin au soir — rythme ancré dans le concret des gestes et des heures.",
            "portrait_individuel": "Portrait intime d'un individu, son parcours, ses pensées, son évolution au fil du récit.",
            "avant_apres_evenement": "Structure en diptyque : la vie avant un événement marquant, puis la transformation après.",
            "mosaique_voix": "Fragments de voix, de souvenirs et de témoignages entrelacés comme un collage sonore.",
            "lettre_intime": "Sous forme de lettre ou de journal intime — ton confidentiel et personnel.",
            "recit_initiatique": "Parcours d'apprentissage ou de découverte — le narrateur entre dans un monde inconnu et le comprend peu à peu.",
        }
        angle_desc = angle_descriptions.get(angle_scenarisation, "")
        angle_section = f"\n- Angle de scénarisation : {angle_scenarisation}\n  → {angle_desc}" if angle_desc else ""

        # Build original prompt section
        prompt_section = ""
        if original_prompt and original_prompt.strip():
            prompt_section = f"\n\nDEMANDE ORIGINALE DE L'UTILISATEUR :\n\"{original_prompt.strip()}\"\n→ Respectez scrupuleusement les intentions et souhaits exprimés ci-dessus."
        
        # Build prompt for Claude
        prompt = f"""Créez une structure narrative complète pour un scénario audio historique.

PARAMÈTRES :
- Durée totale : {duree}s
- Forme : {forme}
- Ton : {ton}
- Public : {public}
- Axe narratif : {axe}
- Structure : {structure_type}
- Rythme : {rythme}
- Perspective narrative : {gen_params.get('perspective_narrative', {}).get('value', 'troisieme_personne')}{angle_section}
{prompt_section}

CONTEXTE HISTORIQUE :
- Période : {hist_context.get('period', {}).get('start_year', 'N/A')}-{hist_context.get('period', {}).get('end_year', 'N/A')}
- Lieu : {hist_context.get('location', {}).get('primary', 'Non spécifié')}
- Thèmes : {', '.join(hist_context.get('themes', {}).get('primary', []))}
{audio_section}

ARC ÉMOTIONNEL (guideline) : {emotional_arc}

MISSION :
1. Décidez librement du nombre de sections (1 à 7) selon ce qui est NATUREL pour ce récit. Un récit court ou intimiste peut n'avoir qu'une seule section continue. Un récit épique peut en avoir 5-7. Ne forcez JAMAIS un découpage artificiel.
2. La somme des durées des sections doit correspondre à la durée totale ({duree}s ± 10%).
3. Pour chaque section, assignez :
   - Une fonction narrative claire
   - Une position sur l'arc émotionnel
   - Une liste d'éléments narratifs nécessaires (incluant les archives audio si disponibles)
   - Un mood général
4. Définissez les transitions clés entre sections (si plus d'une section)
5. Ajoutez des notes de production insistant sur la FLUIDITÉ et la CONTINUITÉ narrative
6. L'angle de scénarisation ("{angle_scenarisation}") définit la MANIÈRE de raconter. Structurez les sections pour servir cet angle.

IMPORTANT : Privilégiez un récit fluide et continu. Les sections sont des repères de rythme, PAS des coupures franches. Le texte final doit couler naturellement d'un bout à l'autre.

Retournez un JSON avec cette structure EXACTE :
{{
  "scenario_id": {scenario_num},
  "titre_global": "Titre captivant du scénario",
  "axe_narratif": "{axe}",
  "angle_scenarisation": "{angle_scenarisation}",
  "duree_totale": {duree},
  "structure": [
    {{
      "partie": 1,
      "titre": "Titre de la section",
      "duree_cible": 60.0,
      "fonction_narrative": "exposition",
      "position_arc_emotionnel": "calme_contemplatif",
      "elements_necessaires": ["element1", "element2", "element3"],
      "mood": "descriptif_neutre"
    }}
  ],
  "arc_emotionnel_global": "{emotional_arc['type']}",
  "rythme_general": "{rythme}",
  "transitions_cles": [
    {{
      "entre_parties": [1, 2],
      "type": "progression_naturelle",
      "duree": 2.0,
      "description": "Description de la transition"
    }}
  ],
  "notes_production": "Instructions pour Agent 2 : insister sur la fluidité narrative et la continuité du récit"
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
            structure = self._extract_json(response_text)
            
            logger.info(f"Structure created: {structure.get('titre_global', 'N/A')}")
            return structure
            
        except Exception as e:
            logger.error(f"Error creating narrative structure: {e}", exc_info=True)
            # Return basic fallback structure
            return self._create_fallback_structure(scenario_num, duree, axe)
    
    def calculate_parts_distribution(
        self,
        total_duration: int,
        public_cible: str,
        rythme: str,
        structure_type: str
    ) -> List[float]:
        """
        Calculate optimal distribution of durations per part.
        
        Args:
            total_duration: Total duration in seconds
            public_cible: Target audience
            rythme: Rhythm type
            structure_type: Structure type
            
        Returns:
            List of durations for each part
        """
        # Determine number of parts based on duration
        if total_duration <= 90:
            num_parts = 2
        elif total_duration <= 180:
            num_parts = 3
        elif total_duration <= 360:
            num_parts = 4
        else:
            num_parts = 5
        
        # Adjust for children (shorter parts)
        if public_cible in ['enfants', 'scolaire_primaire']:
            num_parts = max(num_parts, int(total_duration / 50))  # Max 50s per part
        
        # Apply distribution pattern based on structure
        if structure_type == 'crescendo_emotionnel':
            # Increasing durations
            parts = self._crescendo_distribution(total_duration, num_parts)
        elif structure_type == 'flashback':
            # Present short, flashback long, return short
            if num_parts == 3:
                parts = [total_duration * 0.2, total_duration * 0.6, total_duration * 0.2]
            else:
                parts = self._balanced_distribution(total_duration, num_parts)
        else:
            # Balanced or slightly varied
            parts = self._balanced_distribution(total_duration, num_parts)
        
        return parts
    
    def define_emotional_arc(
        self,
        tone: str,
        structure_type: str,
        duration: float,
        public_cible: str
    ) -> Dict[str, Any]:
        """
        Define emotional arc for the scenario.
        
        Args:
            tone: Tone type
            structure_type: Structure type
            duration: Total duration
            public_cible: Target audience
            
        Returns:
            Emotional arc definition
        """
        # Define arc type based on tone and structure
        if tone in ['dramatique_immersif', 'emotionnel_personnel']:
            arc_type = 'progression_crescendo'
        elif tone == 'contemplatif_poetique':
            arc_type = 'contemplative'
        elif structure_type == 'circulaire':
            arc_type = 'circulaire'
        else:
            arc_type = 'tension_resolution'
        
        # Define key emotional points
        if arc_type == 'progression_crescendo':
            points = [
                {"position": 0.0, "etat": "calme", "intensite": 0.2},
                {"position": 0.4, "etat": "tension_montante", "intensite": 0.5},
                {"position": 0.75, "etat": "climax", "intensite": 0.9},
                {"position": 1.0, "etat": "resolution", "intensite": 0.4}
            ]
        elif arc_type == 'contemplative':
            points = [
                {"position": 0.0, "etat": "calme", "intensite": 0.3},
                {"position": 0.5, "etat": "reflection", "intensite": 0.5},
                {"position": 1.0, "etat": "contemplation", "intensite": 0.4}
            ]
        elif arc_type == 'circulaire':
            points = [
                {"position": 0.0, "etat": "debut", "intensite": 0.3},
                {"position": 0.3, "etat": "exploration", "intensite": 0.6},
                {"position": 0.7, "etat": "revelation", "intensite": 0.8},
                {"position": 1.0, "etat": "retour_transforme", "intensite": 0.3}
            ]
        else:  # tension_resolution
            points = [
                {"position": 0.0, "etat": "setup", "intensite": 0.3},
                {"position": 0.2, "etat": "tension", "intensite": 0.7},
                {"position": 0.6, "etat": "climax", "intensite": 0.9},
                {"position": 1.0, "etat": "resolution", "intensite": 0.3}
            ]
        
        return {
            'type': arc_type,
            'points_cles': points
        }
    
    def _balanced_distribution(self, total: float, num_parts: int) -> List[float]:
        """Create balanced distribution."""
        base = total / num_parts
        return [base] * num_parts
    
    def _crescendo_distribution(self, total: float, num_parts: int) -> List[float]:
        """Create crescendo distribution (increasing parts)."""
        # Create weights that increase: 1, 1.5, 2, 2.5...
        weights = [1 + (i * 0.5) for i in range(num_parts)]
        total_weight = sum(weights)
        
        return [(w / total_weight) * total for w in weights]
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from response."""
        import re
        
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try markdown code block
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
    
    def _create_fallback_structure(
        self,
        scenario_id: int,
        duree: float,
        axe: str,
        parts_durations: Optional[List[float]] = None
    ) -> Dict:
        """Create fallback structure if Claude fails.
        
        Uses a simple 2-section structure (intro + development) for
        short durations and 3 sections for longer ones.
        """
        logger.warning("Creating fallback structure")
        
        # Simple adaptive split
        if duree <= 120:
            parts_durations = [duree * 0.4, duree * 0.6]
            functions = ['exposition', 'développement']
            moods = ['calme', 'intense']
        else:
            parts_durations = [duree * 0.25, duree * 0.50, duree * 0.25]
            functions = ['exposition', 'développement', 'résolution']
            moods = ['calme', 'intense', 'apaisement']
        
        structure = []
        for i in range(len(parts_durations)):
            structure.append({
                'partie': i + 1,
                'titre': f'Section {i + 1}',
                'duree_cible': parts_durations[i],
                'fonction_narrative': functions[i],
                'position_arc_emotionnel': moods[i],
                'elements_necessaires': ['contexte', 'action', 'transition'],
                'mood': moods[i]
            })
        
        return {
            'scenario_id': scenario_id,
            'titre_global': 'Scénario historique',
            'axe_narratif': axe,
            'duree_totale': duree,
            'structure': structure,
            'arc_emotionnel_global': 'progression_crescendo',
            'rythme_general': 'modere',
            'transitions_cles': [],
            'notes_production': 'Structure générée automatiquement — privilégier la fluidité narrative'
        }
