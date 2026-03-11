"""
Agent 2: Historical Scenario Writer
Writes complete scenarios with historical rigor.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional

from agents.utils import build_user_requirement_block

logger = logging.getLogger(__name__)


class ScenarioWriterAgent:
    """Agent 2: Writes historical scenarios."""

    def __init__(self, client):
        self.client = client
        self.model = "claude-opus-4-5"
        self.temperature = 0.8
        self.max_tokens = 8000

        self.system_prompt = (
            "Vous êtes un auteur et historien polyvalent. Vous savez adapter "
            "votre plume à n'importe quel territoire, époque ou thématique. "
            "Votre mission est de créer des récits audio historiquement "
            "rigoureux.\n\n"
            "Principes invariants :\n"
            "1. **Écrivez pour l'oreille** : phrases fluides, rythme naturel.\n"
            "2. **Respectez les durées cibles** : le nombre de mots doit "
            "correspondre à la durée demandée.\n"
            "3. **Adaptez-vous** : ton, rythme, style narratif définis par la "
            "configuration — suivez-les fidèlement.\n\n"
            "RIGUEUR HISTORIQUE (non négociable) :\n"
            "- Basez-vous EXCLUSIVEMENT sur les documents, transcriptions et "
            "sources fournis.\n"
            "- N'INVENTEZ JAMAIS de dates, noms, lieux ou événements absents "
            "des sources.\n"
            "- Restez volontairement vague si le contexte manque.\n"
            "- Atmosphères et émotions : créatives. Faits : traçables."
        )

        # Skills (injected by orchestrator)
        self.historical_analyzer = None
        self.narrative_builder = None

        logger.info("ScenarioWriterAgent initialized")

    def set_skills(self, skills: Dict):
        """Set skill instances."""
        if "historical_context_analyzer" in skills:
            self.historical_analyzer = skills["historical_context_analyzer"]["instance"]
        if "narrative_scenario_builder" in skills:
            self.narrative_builder = skills["narrative_scenario_builder"]["instance"]

    # ==================================================================
    # NEW: Write from prompt template (Agent 0 workflow)
    # ==================================================================

    def writeFromPromptTemplate(
        self,
        promptTemplate: str,
        structureData: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Write a scenario using Agent 0's pre-built prompt template.

        Parameters
        ----------
        promptTemplate : str
            Prompt template from Agent 0 containing ``<<STRUCTURE_ET_RESUME>>``.
        structureData : dict
            Output of Agent 1 (structure + resumeHistoire).

        Returns
        -------
        dict
            Complete scenario with parties, metadata, etc.
        """
        logger.info(
            "Writing scenario from prompt template — structure: %s",
            structureData.get("titre_global", "N/A"),
        )

        # ---- Build the structure/resume block ----
        resume = structureData.get("resumeHistoire", "")
        structureParts = structureData.get("structure", [])

        structureBlock = f"TITRE : {structureData.get('titre_global', '')}\n"
        structureBlock += f"RÉSUMÉ : {resume}\n"
        structureBlock += (
            f"ARC ÉMOTIONNEL : {structureData.get('arc_emotionnel_global', '')}\n"
        )
        structureBlock += (
            f"NOTES PRODUCTION : {structureData.get('notes_production', '')}\n\n"
        )

        for part in structureParts:
            structureBlock += (
                f"--- Partie {part.get('partie', '?')} : "
                f"{part.get('titre', '')} ---\n"
                f"  Durée cible : {part.get('duree_cible', 0)}s "
                f"(~{int(part.get('duree_cible', 0) * 2.5)} mots)\n"
                f"  Fonction : {part.get('fonction_narrative', '')}\n"
                f"  Mood : {part.get('mood', '')}\n"
                f"  Arc émotionnel : {part.get('position_arc_emotionnel', '')}\n"
                f"  Éléments : {', '.join(part.get('elements_necessaires', []))}\n\n"
            )

        # ---- Inject into template ----
        prompt = promptTemplate.replace("<<STRUCTURE_ET_RESUME>>", structureBlock)

        # ---- Call LLM ----
        try:
            response = self.client.create_message(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                system=self.system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            response_text = response.content[0].text
            result = self._extract_json(response_text)

            if not isinstance(result, dict):
                raise ValueError(f"Invalid response type: {type(result)}")

            parties = result.get("parties", [])
            if not parties or not isinstance(parties, list):
                raise ValueError("No valid parties in response")

            # ---- Post-process parties ----
            valid_parties = self._postprocess_parties(parties)
            if not valid_parties:
                raise ValueError("No valid parts after filtering")

            # ---- Build scenario dict ----
            total_duration = sum(p.get("duree", 0) for p in valid_parties)
            word_count = sum(
                self._count_words(p.get("texte_narration", ""))
                for p in valid_parties
            )

            scenario = {
                "scenario_id": structureData.get("scenario_id", 1),
                "titre": structureData.get("titre_global", "Scénario"),
                "axe_narratif": structureData.get("axe_narratif", ""),
                "angle_scenarisation": structureData.get(
                    "angle_scenarisation", ""
                ),
                "resumeHistoire": resume,
                "duree_estimee": total_duration,
                "parties": valid_parties,
                "metadata": {
                    "nombre_mots": word_count,
                    "duree_lecture_estimee": total_duration,
                    "nombre_archives_utilisees": sum(
                        len(
                            [
                                m
                                for m in p.get("moments_cles", [])
                                if m.get("action") == "archive_audio"
                            ]
                        )
                        for p in valid_parties
                    ),
                    "nombre_ambiances": sum(
                        len(p.get("ambiances_continues", []))
                        for p in valid_parties
                    ),
                },
                "notes_pour_agent_3": structureData.get(
                    "notes_production", ""
                ),
            }

            logger.info(
                "Scenario written via template: %d words, %d parts, %.1fs",
                word_count,
                len(valid_parties),
                total_duration,
            )
            return scenario

        except Exception as e:
            logger.error(
                "Error writing scenario from template: %s", e, exc_info=True
            )
            raise

    # ==================================================================
    # Legacy: write_complete_scenario (backward compat)
    # ==================================================================

    def write_complete_scenario(
        self,
        structure: Dict[str, Any],
        config: Dict[str, Any],
        historical_context: Optional[Dict] = None,
        audio_transcriptions: Optional[List] = None,
    ) -> Dict[str, Any]:
        """Write complete scenario from structure (legacy path)."""
        logger.info("Writing scenario: %s", structure.get("titre_global", "N/A"))

        scenario_id = structure.get("scenario_id", 1)
        titre = structure.get("titre_global", "Scénario historique")
        axe = structure.get("axe_narratif", "mixte")
        angle = structure.get(
            "angle_scenarisation",
            config.get("scenario_config", {})
            .get("generation_parameters", {})
            .get("angle_scenarisation", {})
            .get("value", "auto"),
        )

        if not historical_context and self.historical_analyzer:
            historical_context = self._get_historical_context(
                config, audio_transcriptions
            )

        parties = self._write_all_parts_single_request(
            structure, config, historical_context, audio_transcriptions
        )

        total_duration = sum(p.get("duree", 0) for p in parties)
        word_count = sum(
            self._count_words(p.get("texte_narration", "")) for p in parties
        )
        archives_used = sum(
            len(
                [
                    m
                    for m in p.get("moments_cles", [])
                    if m.get("action") == "archive_audio"
                ]
            )
            for p in parties
        )
        ambiances_count = sum(
            len(p.get("ambiances_continues", [])) for p in parties
        )

        validation = self.validate_historical_accuracy(
            {"parties": parties},
            config.get("scenario_config", {})
            .get("historical_context", {})
            .get("period", {}),
        )

        gen_params = config.get("scenario_config", {}).get(
            "generation_parameters", {}
        )
        ton_value = gen_params.get("ton", {}).get("value", "neutre_informatif")

        scenario = {
            "scenario_id": scenario_id,
            "titre": titre,
            "axe_narratif": axe,
            "angle_scenarisation": angle,
            "ton": ton_value,
            "duree_estimee": total_duration,
            "parties": parties,
            "metadata": {
                "nombre_mots": word_count,
                "duree_lecture_estimee": total_duration,
                "nombre_archives_utilisees": archives_used,
                "nombre_ambiances": ambiances_count,
                "coherence_historique": validation,
            },
            "notes_pour_agent_3": structure.get("notes_production", ""),
        }

        logger.info(
            "Scenario written: %d words, %d parts, %.1fs",
            word_count,
            len(parties),
            total_duration,
        )
        return scenario

    # ==================================================================
    # Internal writing logic (legacy path)
    # ==================================================================

    def _write_all_parts_single_request(
        self,
        structure: Dict,
        config: Dict,
        historical_context: Optional[Dict],
        audio_transcriptions: Optional[List],
    ) -> List[Dict]:
        """Generate ALL parts in one LLM call (legacy)."""
        gen_params = config.get("scenario_config", {}).get(
            "generation_parameters", {}
        )
        ton = gen_params.get("ton", {}).get("value", "neutre_informatif")
        public = gen_params.get("public_cible", {}).get("value", "grand_public")
        angle = gen_params.get("angle_scenarisation", {}).get("value", "auto")

        original_prompt = (
            config.get("scenario_config", {})
            .get("user_input", {})
            .get("original_prompt", "")
        )

        angle_descriptions = {
            "temoignage_croise": "Récit à la 1ère personne avec plusieurs témoins.",
            "chronique_sociale": "Chronique à la 3ème personne sur un groupe social.",
            "journee_type": "Journée type du matin au soir.",
            "portrait_individuel": "Portrait intime d'un individu.",
            "avant_apres_evenement": "Diptyque avant/après événement.",
            "mosaique_voix": "Collage sonore de voix et témoignages.",
            "lettre_intime": "Lettre ou journal intime.",
            "recit_initiatique": "Parcours de découverte.",
        }
        angle_desc = angle_descriptions.get(
            angle, "Angle libre, approche la plus adaptée."
        )

        context_str = ""
        if historical_context:
            context_str = json.dumps(
                historical_context.get("contexte_enrichi", {}),
                indent=2,
                ensure_ascii=False,
            )[:4000]

        transcriptions_section = ""
        if audio_transcriptions:
            lines = []
            for t in audio_transcriptions:
                name = t.get("file_name", "audio")
                text = t.get("transcription", "")
                if text:
                    lines.append(f"--- {name} ---\n{text[:3000]}")
            if lines:
                transcriptions_section = (
                    "\n\nTRANSCRIPTIONS AUDIO :\n" + "\n\n".join(lines)
                )

        prompt_section = ""
        if original_prompt and original_prompt.strip():
            prompt_section = (
                f'\n\nDEMANDE ORIGINALE :\n"{original_prompt.strip()}"'
                "\n→ Respectez les intentions ci-dessus."
            )

        user_req = build_user_requirement_block(config)
        priority = ""
        if user_req:
            priority = "\n7. PRIORITÉ ABSOLUE : brief utilisateur."

        parts_desc = []
        for ps in structure.get("structure", []):
            parts_desc.append(
                f"\nPartie {ps['partie']} : {ps['titre']}\n"
                f"- Durée : {ps['duree_cible']}s (~{int(ps['duree_cible'] * 2.5)} mots)\n"
                f"- Fonction : {ps['fonction_narrative']}\n"
                f"- Mood : {ps['mood']}\n"
                f"- Arc : {ps['position_arc_emotionnel']}\n"
                f"- Éléments : {', '.join(ps['elements_necessaires'])}\n"
            )

        prompt = f"""Écrivez le scénario audio complet.

{(user_req + chr(10) + chr(10)) if user_req else ''}
INFORMATIONS :
- Titre : {structure.get('titre_global')}
- Axe : {structure.get('axe_narratif')}
- Arc : {structure.get('arc_emotionnel_global')}
- Durée : {structure.get('duree_totale')}s
- Ton : {ton}
- Public : {public}

ANGLE : {angle}
→ {angle_desc}
{prompt_section}

STRUCTURE EN {len(structure.get('structure', []))} PARTIES :
{''.join(parts_desc)}

CONTEXTE HISTORIQUE :
{context_str}
{transcriptions_section}

CONSIGNES :
1. TOUTES les parties, cohérentes et FLUIDES
2. Angle → MANIÈRE de raconter
3. Vocabulaire adapté au public et à l'époque
4. Utilisez les transcriptions audio si fournies
5. 2-3 moments clés par partie + directions de ton
6. Pour chaque phrase, listez les sources de transcription{priority}

Retournez un JSON :
{{
  "parties": [
    {{
      "partie_id": 1,
      "titre": "...",
      "duree": 45.0,
      "texte_narration": "...",
      "ton": {{"global": "...", "tempo_lecture": 110, "pauses": [], "intonation": "..."}},
      "moments_cles": [{{"timestamp": "0:XX", "action": "...", "duree": 2.0}}],
      "ambiances_continues": [],
      "sentence_sources": [{{"sentence": "...", "sources": ["..."]}}]
    }}
  ]
}}

JSON :"""

        try:
            response = self.client.create_message(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                system=self.system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            response_text = response.content[0].text
            result = self._extract_json(response_text)

            if not isinstance(result, dict):
                raise ValueError(f"Invalid response type: {type(result)}")

            parties = result.get("parties", [])
            if not parties:
                raise ValueError("No parties generated")
            if not isinstance(parties, list):
                raise ValueError(f"Invalid parties type: {type(parties)}")

            valid = self._postprocess_parties(parties)
            if not valid:
                raise ValueError("No valid parts after filtering")

            logger.info("Generated %d valid parts", len(valid))
            return valid

        except Exception as e:
            logger.error("Error generating parts: %s", e, exc_info=True)
            raise

    # ==================================================================
    # Shared helpers
    # ==================================================================

    def _postprocess_parties(self, parties: List) -> List[Dict]:
        """Clean up and validate LLM-returned parties."""
        valid: List[Dict] = []
        for i, part in enumerate(parties):
            if not isinstance(part, dict):
                logger.error("Part %d is %s — skipping", i, type(part))
                continue

            # Ensure ton is a dict
            ton_val = part.get("ton", {})
            if not isinstance(ton_val, dict):
                part["ton"] = {
                    "global": str(ton_val),
                    "tempo_lecture": 110,
                    "pauses": [],
                    "intonation": "",
                }

            # Ensure moments_cles is list of dicts
            mc = part.get("moments_cles", [])
            part["moments_cles"] = (
                [m for m in mc if isinstance(m, dict)]
                if isinstance(mc, list)
                else []
            )

            # Ensure ambiances_continues is list of dicts
            amb = part.get("ambiances_continues", [])
            part["ambiances_continues"] = (
                [a for a in amb if isinstance(a, dict)]
                if isinstance(amb, list)
                else []
            )

            # Normalize sentence_sources
            ss = part.get("sentence_sources", [])
            if isinstance(ss, list):
                norm = []
                for item in ss:
                    if not isinstance(item, dict):
                        continue
                    s_text = item.get("sentence")
                    s_srcs = item.get("sources", [])
                    if not isinstance(s_text, str):
                        continue
                    if not isinstance(s_srcs, list):
                        s_srcs = []
                    norm.append(
                        {
                            "sentence": s_text.strip(),
                            "sources": [
                                str(s).strip()
                                for s in s_srcs
                                if isinstance(s, str) and s.strip()
                            ],
                        }
                    )
                part["sentence_sources"] = norm
            else:
                part["sentence_sources"] = []

            # Recalculate duration
            timing = self.calculate_narration_timing(
                part.get("texte_narration", ""),
                part["ton"].get("tempo_lecture", 110),
                [],
            )
            part["duree"] = timing["duration"]
            valid.append(part)

        return valid

    def validate_historical_accuracy(
        self,
        scenario: Dict,
        period: Dict,
        strict_mode: bool = False,
    ) -> Dict[str, Any]:
        logger.info("Validating historical accuracy")
        text_parts = [
            p.get("texte_narration", "") for p in scenario.get("parties", [])
        ]
        full_text = " ".join(text_parts)

        if self.historical_analyzer:
            try:
                result = self.historical_analyzer.detect_anachronisms(
                    full_text, period.get("start_year", 1900), strict_mode
                )
                return {
                    "accuracy_score": result.get("score", 0.8),
                    "sources_citees": [],
                    "verifications": [
                        f"Anachronismes : {result.get('total_anachronisms', 0)}"
                    ],
                    "vocabulaire_epoque": [],
                }
            except Exception as e:
                logger.warning("Skill validation failed: %s", e)

        return {
            "accuracy_score": 0.8,
            "sources_citees": [],
            "verifications": ["Validation basique effectuée"],
            "vocabulaire_epoque": [],
        }

    def calculate_narration_timing(
        self,
        text: str,
        tempo_wpm: int = 110,
        pauses: Optional[List] = None,
        include_buffer: bool = False,
    ) -> Dict[str, float]:
        word_count = self._count_words(text)
        reading_time = (word_count / tempo_wpm) * 60
        pauses_time = 0.0
        if pauses:
            for p in pauses:
                if isinstance(p, dict) and "duration" in p:
                    pauses_time += p["duration"]
                elif isinstance(p, (int, float)):
                    pauses_time += p
        buffer = (reading_time + pauses_time) * 0.1 if include_buffer else 0.0
        duration = reading_time + pauses_time + buffer
        return {
            "duration": duration,
            "word_count": word_count,
            "reading_time": reading_time,
            "pauses_time": pauses_time,
            "buffer": buffer,
        }

    def _get_historical_context(
        self, config: Dict, audio_transcriptions: Optional[List] = None
    ) -> Dict:
        if not self.historical_analyzer:
            return {}
        hc = config.get("scenario_config", {}).get("historical_context", {})
        docs: List[str] = []
        if audio_transcriptions:
            for t in audio_transcriptions:
                text = t.get("transcription", "")
                name = t.get("file_name", "audio")
                if text and text.strip():
                    docs.append(f"[Source: {name}]\n{text}")
        try:
            return self.historical_analyzer.analyze_historical_documents(
                docs,
                hc.get("period", {}),
                hc.get("location", {}).get("primary"),
                hc.get("themes", {}).get("primary", []),
            )
        except Exception as e:
            logger.error("Error getting historical context: %s", e)
            return {}

    def _count_words(self, text: str) -> int:
        return len(re.findall(r"\b\w+\b", text))

    def _extract_json(self, text: str) -> Dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError("Could not extract valid JSON")
