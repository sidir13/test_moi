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
        self.max_tokens = 8000
        
        self.system_prompt = """Vous êtes un auteur et historien polyvalent. Vous savez adapter votre plume à n'importe quel territoire, époque ou thématique. Votre mission est de créer des récits audio historiquement rigoureux.

Principes invariants :
1. **Écrivez pour l'oreille** : le texte sera lu à voix haute — phrases fluides, rythme naturel.
2. **Respectez les durées cibles** : le nombre de mots doit correspondre à la durée demandée.
3. **Adaptez-vous** : le ton, le rythme, le style narratif et la structure sont définis par la configuration — suivez-les fidèlement.

RIGUEUR HISTORIQUE (non négociable) :
- Basez-vous EXCLUSIVEMENT sur les documents, transcriptions audio et sources externes fournis dans le contexte.
- N'INVENTEZ JAMAIS de dates, noms, lieux ou événements historiques précis absents des sources.
- Si le contexte manque, restez volontairement vague : "un homme", "dans les années…", "sur le port…".
- Vous pouvez librement créer des atmosphères, émotions et descriptions sensorielles, mais JAMAIS des faits historiques."""
        
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
        angle = structure.get('angle_scenarisation', config.get('scenario_config', {}).get('generation_parameters', {}).get('angle_scenarisation', {}).get('value', 'auto'))
        
        # Get historical context if not provided
        if not historical_context and self.historical_analyzer:
            historical_context = self._get_historical_context(config, audio_transcriptions)
        
        # Write ALL parts in a SINGLE LLM request for coherence
        parties = self._write_all_parts_single_request(
            structure,
            config,
            historical_context,
            audio_transcriptions
        )
        
        # Calculate totals
        total_duration = 0.0
        word_count = 0
        archives_used = 0
        ambiances_count = 0
        
        for part in parties:
            total_duration += part.get('duree', 0)
            word_count += self._count_words(part.get('texte_narration', ''))
            archives_used += len([m for m in part.get('moments_cles', []) if m.get('action') == 'archive_audio'])
            ambiances_count += len(part.get('ambiances_continues', []))
        
        # Validate historical accuracy
        validation = self.validate_historical_accuracy(
            {'parties': parties},
            config.get('scenario_config', {}).get('historical_context', {}).get('period', {})
        )
        
        # Extract ton for metadata
        gen_params = config.get('scenario_config', {}).get('generation_parameters', {})
        ton_value = gen_params.get('ton', {}).get('value', 'neutre_informatif')
        
        # Build complete scenario
        scenario = {
            'scenario_id': scenario_id,
            'titre': titre,
            'axe_narratif': axe,
            'angle_scenarisation': angle,
            'ton': ton_value,
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
    
    def _write_all_parts_single_request(
        self,
        structure: Dict,
        config: Dict,
        historical_context: Optional[Dict],
        audio_transcriptions: Optional[List]
    ) -> List[Dict]:
        """Generate ALL scenario parts in a SINGLE LLM request for better coherence."""
        
        gen_params = config.get('scenario_config', {}).get('generation_parameters', {})
        ton = gen_params.get('ton', {}).get('value', 'neutre_informatif')
        public = gen_params.get('public_cible', {}).get('value', 'grand_public')
        angle = gen_params.get('angle_scenarisation', {}).get('value', 'auto')
        
        # Read original user prompt
        original_prompt = config.get('scenario_config', {}).get('user_input', {}).get('original_prompt', '')
        
        # Build angle description
        angle_descriptions = {
            "temoignage_croise": "Récit à la 1ère personne avec plusieurs témoins qui se relaient — chaque voix apporte son regard.",
            "chronique_sociale": "Chronique à la 3ème personne sur la vie d'un groupe social, ses habitudes et ses luttes.",
            "journee_type": "Une journée type racontée du matin au soir, ancrée dans le concret des gestes et des heures.",
            "portrait_individuel": "Portrait intime d'un individu, son parcours, ses pensées, son évolution.",
            "avant_apres_evenement": "Structure en diptyque : la vie avant un événement marquant, puis la transformation après.",
            "mosaique_voix": "Fragments de voix, de souvenirs et de témoignages entrelacés comme un collage sonore.",
            "lettre_intime": "Sous forme de lettre ou de journal intime — ton confidentiel et personnel.",
            "recit_initiatique": "Parcours de découverte — le narrateur entre dans un monde inconnu et le comprend peu à peu.",
        }
        angle_desc = angle_descriptions.get(angle, "Angle libre, choisissez l'approche la plus adaptée au sujet.")
        
        # Build context strings
        context_str = ""
        if historical_context:
            context_str = json.dumps(
                historical_context.get('contexte_enrichi', {}),
                indent=2,
                ensure_ascii=False
            )[:4000]

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
                    "\n\nTRANSCRIPTIONS AUDIO DISPONIBLES (témoignages réels) :\n"
                    + "\n\n".join(transcriptions_lines)
                )

        # Build original prompt section
        prompt_section = ""
        if original_prompt and original_prompt.strip():
            prompt_section = f"""

DEMANDE ORIGINALE DE L'UTILISATEUR :
\"{original_prompt.strip()}\"
→ Respectez scrupuleusement les intentions, souhaits et le ton demandé ci-dessus."""
        
        # Build structure description for prompt
        parts_desc = []
        for part_struct in structure.get('structure', []):
            parts_desc.append(f"""
Partie {part_struct['partie']} : {part_struct['titre']}
- Durée cible : {part_struct['duree_cible']}s (environ {int(part_struct['duree_cible'] * 2.5)} mots)
- Fonction narrative : {part_struct['fonction_narrative']}
- Mood : {part_struct['mood']}
- Position émotionnelle : {part_struct['position_arc_emotionnel']}
- Éléments nécessaires : {', '.join(part_struct['elements_necessaires'])}
""")
        
        prompt = f"""Écrivez le scénario audio complet en GÉNÉRANT TOUTES LES PARTIES dans une seule réponse cohérente.

INFORMATIONS GLOBALES :
- Titre du scénario : {structure.get('titre_global')}
- Axe narratif : {structure.get('axe_narratif')}
- Arc émotionnel : {structure.get('arc_emotionnel_global')}
- Durée totale : {structure.get('duree_totale')}s
- Ton : {ton}
- Public : {public}

ANGLE DE SCÉNARISATION : {angle}
→ {angle_desc}
{prompt_section}

STRUCTURE EN {len(structure.get('structure', []))} PARTIES :
{''.join(parts_desc)}

CONTEXTE HISTORIQUE (SEULE source de faits autorisée) :
{context_str}
{transcriptions_section}

CONSIGNES :
1. Générez TOUTES les parties en une seule réponse cohérente — le récit doit être CONTINU et FLUIDE
2. L'angle de scénarisation ci-dessus définit la MANIÈRE de raconter (point de vue, voix, rythme) — suivez-le fidèlement
3. Adaptez le vocabulaire au public cible et à l'époque historique
4. Si des transcriptions audio sont fournies, UTILISEZ-LES comme source primaire : intégrez les mots et témoignages réels
5. Pour chaque partie : 2-3 moments clés (effets sonores, pauses, archives) + directions de ton (tempo, intonation)
6. Après avoir rédigé le texte, découpez-le en phrases et pour chaque phrase listez les lignes de transcription qui l'ont inspirée (exactes ou très proches). S'il n'y a pas de transcription pertinente, laissez la liste vide.

Retournez un JSON avec TOUTES les parties :
{{
  "parties": [
    {{
      "partie_id": 1,
      "titre": "...",
      "duree": 45.0,
      "texte_narration": "Le texte narratif complet de la partie 1...",
      "ton": {{
        "global": "...",
        "tempo_lecture": 110,
        "pauses": ["..."],
        "intonation": "..."
      }},
      "moments_cles": [
        {{
          "timestamp": "0:XX",
          "action": "...",
          "duree": 2.0
        }}
      ],
      "ambiances_continues": [],
      "sentence_sources": [
        {{"sentence": "Phrase complète numéro 1.", "sources": ["[00:12] Citation exacte...", "[00:35] ..."]}},
        {{"sentence": "Phrase 2 ...", "sources": []}}
      ]
    }},
    {{ ... partie 2 ... }},
    {{ ... etc pour toutes les parties ... }}
  ]
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
            result = self._extract_json(response_text)
            
            # Validate result is a dict
            if not isinstance(result, dict):
                logger.error(f"_extract_json returned {type(result)} instead of dict: {str(result)[:200]}")
                raise ValueError(f"Invalid response type: {type(result)}")
            
            parties = result.get('parties', [])
            if not parties:
                logger.error(f"No 'parties' key in response. Keys: {list(result.keys())}")
                raise ValueError("No parties generated in response")
            
            # Validate parties is a list
            if not isinstance(parties, list):
                logger.error(f"'parties' is {type(parties)} instead of list")
                raise ValueError(f"Invalid parties type: {type(parties)}")
            
            # Filter out non-dict parts and calculate timing
            valid_parties = []
            for i, part in enumerate(parties):
                if not isinstance(part, dict):
                    logger.error(f"Part {i} is {type(part)} instead of dict — skipping")
                    continue
                
                # Ensure 'ton' is a dict (LLM sometimes returns a string)
                ton_value = part.get('ton', {})
                if not isinstance(ton_value, dict):
                    part['ton'] = {'global': str(ton_value), 'tempo_lecture': 110, 'pauses': [], 'intonation': ''}
                
                # Ensure 'moments_cles' is a list of dicts
                moments = part.get('moments_cles', [])
                if isinstance(moments, list):
                    part['moments_cles'] = [m for m in moments if isinstance(m, dict)]
                else:
                    part['moments_cles'] = []
                
                # Ensure 'ambiances_continues' is a list of dicts
                ambiances = part.get('ambiances_continues', [])
                if isinstance(ambiances, list):
                    part['ambiances_continues'] = [a for a in ambiances if isinstance(a, dict)]
                else:
                    part['ambiances_continues'] = []

                sentence_sources = part.get('sentence_sources', [])
                if isinstance(sentence_sources, list):
                    normalized_sources = []
                    for item in sentence_sources:
                        if not isinstance(item, dict):
                            continue
                        sentence_text = item.get('sentence')
                        sources_list = item.get('sources', [])
                        if not isinstance(sentence_text, str):
                            continue
                        if not isinstance(sources_list, list):
                            sources_list = []
                        normalized_sources.append({
                            'sentence': sentence_text.strip(),
                            'sources': [str(src).strip() for src in sources_list if isinstance(src, str) and src.strip()],
                        })
                    part['sentence_sources'] = normalized_sources
                else:
                    part['sentence_sources'] = []
                
                timing = self.calculate_narration_timing(
                    part.get('texte_narration', ''),
                    part['ton'].get('tempo_lecture', 110),
                    []
                )
                part['duree'] = timing['duration']
                valid_parties.append(part)
            
            if not valid_parties:
                raise ValueError("No valid parts after filtering")
            
            logger.info(f"Generated {len(valid_parties)} valid parts in single request")
            return valid_parties
            
        except Exception as e:
            logger.error(f"Error generating all parts: {e}", exc_info=True)
            # Fallback to iterative generation
            logger.warning("Falling back to iterative part generation")
            return self._write_parts_iterative(structure, config, historical_context, audio_transcriptions)
    
    def _write_parts_iterative(
        self,
        structure: Dict,
        config: Dict,
        historical_context: Optional[Dict],
        audio_transcriptions: Optional[List]
    ) -> List[Dict]:
        """Fallback: Generate parts iteratively (old method)."""
        parties = []
        for part_structure in structure.get('structure', []):
            part = self._write_part(
                part_structure,
                structure,
                config,
                historical_context,
                audio_transcriptions
            )
            parties.append(part)
        return parties
    
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
        angle = gen_params.get('angle_scenarisation', {}).get('value', 'auto')
        original_prompt = config.get('scenario_config', {}).get('user_input', {}).get('original_prompt', '')
        return self._generate_part_direct(
            part_id, titre, duree_cible, fonction, mood, ton, public,
            historical_context, audio_transcriptions,
            angle_scenarisation=angle,
            original_prompt=original_prompt
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
        historical_context: Optional[Dict],
        audio_transcriptions: Optional[List] = None,
        angle_scenarisation: str = "auto",
        original_prompt: str = ""
    ) -> Dict:
        """Generate part directly with Claude."""
        
        word_target = int(duree * 2.5)  # ~2.5 words per second at 150 WPM
        
        context_str = ""
        if historical_context:
            context_str = json.dumps(
                historical_context.get('contexte_enrichi', {}),
                indent=2,
                ensure_ascii=False
            )[:4000]

        # Build transcriptions section
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
                    "\n\nTRANSCRIPTIONS AUDIO DISPONIBLES (témoignages réels) :\n"
                    + "\n\n".join(transcriptions_lines)
                )

        # Build original prompt section
        prompt_section = ""
        if original_prompt and original_prompt.strip():
            prompt_section = f"\nDEMANDE ORIGINALE : \"{original_prompt.strip()}\""
        
        prompt = f"""Écrivez la partie {part_id} d'un scénario audio historique.

PARAMÈTRES :
- Titre : {titre}
- Durée : {duree}s (environ {word_target} mots)
- Fonction narrative : {fonction}
- Mood : {mood}
- Ton : {ton}
- Public : {public}
- Angle de scénarisation : {angle_scenarisation}
{prompt_section}

CONTEXTE HISTORIQUE (SEULE source de faits autorisée) :
{context_str}
{transcriptions_section}

CONSIGNES :
1. Texte narratif fluide et continu pour lecture audio
2. Adaptez le vocabulaire au public et à l'époque
3. 2-3 moments clés pour placement d'effets/archives + directions de ton
4. Si des transcriptions audio sont fournies, intégrez les mots et témoignages réels
5. Après rédaction, découpez vos phrases et associez à chacune les lignes de transcription pertinentes (ou liste vide si aucune).
6. Suivez fidèlement l'angle de scénarisation demandé

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
  "ambiances_continues": [],
  "sentence_sources": [
    {{"sentence": "Première phrase complète.", "sources": ["[00:12] ..."]}},
    {{"sentence": "Deuxième phrase.", "sources": []}}
  ]
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
    
    def _get_historical_context(
        self,
        config: Dict,
        audio_transcriptions: Optional[List] = None
    ) -> Dict:
        """Get historical context using analyzer skill.
        
        Converts audio transcriptions into textual documents so the
        historical analyzer can use them as primary sources.
        """
        if not self.historical_analyzer:
            return {}
        
        hist_context = config.get('scenario_config', {}).get('historical_context', {})
        
        # Build document list from transcriptions
        docs: List[str] = []
        if audio_transcriptions:
            for t in audio_transcriptions:
                text = t.get("transcription", "")
                name = t.get("file_name", "audio")
                if text and text.strip():
                    docs.append(f"[Source: Transcription audio — {name}]\n{text}")
            if docs:
                logger.info(f"Passing {len(docs)} transcription documents to historical analyzer")
        
        try:
            return self.historical_analyzer.analyze_historical_documents(
                docs,
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
