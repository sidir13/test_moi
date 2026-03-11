"""
Agent 1: Narrative Structure Architect
Creates narrative structures (+ story summary) for scenarios.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional

from agents.utils import build_user_requirement_block

logger = logging.getLogger(__name__)


class StructureArchitectAgent:
    """Agent 1: Creates narrative structure architecture + story summary."""

    def __init__(self, client):
        self.client = client
        self.model = "claude-sonnet-4-5"
        self.temperature = 0.7
        self.max_tokens = 4000

        self.system_prompt = (
            "Vous êtes un architecte narratif spécialisé en récits audio "
            "historiques. Votre expertise est la construction de structures "
            "narratives solides, émotionnellement engageantes et adaptées au "
            "format audio.\n\n"
            "Principes de conception :\n"
            "1. **Cohérence temporelle** : Respectez strictement la durée cible\n"
            "2. **Arc émotionnel** : Créez une progression émotionnelle claire\n"
            "3. **Rythme audio** : Variez intensité et tempo\n"
            "4. **Fluidité narrative** : Le récit doit couler naturellement, "
            "sans ruptures artificielles entre sections\n"
            "5. **Adaptation au public** : Ajustez complexité selon l'audience\n"
            "6. **Liberté structurelle** : 1 à 7 sections selon le récit\n"
            "7. **Résumé d'histoire** : Vous fournissez toujours un résumé "
            "narratif de 3-5 phrases (resumeHistoire) décrivant l'histoire "
            "qui sera écrite\n\n"
            "RÈGLE ABSOLUE — RIGUEUR HISTORIQUE :\n"
            "- N'INVENTEZ JAMAIS de dates, noms, lieux ou événements absents "
            "du contexte fourni.\n"
            "- Les éléments narratifs (atmosphères, émotions) peuvent être "
            "créatifs, mais les FAITS doivent être traçables aux sources."
        )

        logger.info("StructureArchitectAgent initialized")

    # ==================================================================
    # NEW: Create structure from pre-built prompt (Agent 0 workflow)
    # ==================================================================

    def createStructureFromPrompt(self, prompt: str) -> Dict[str, Any]:
        """Create narrative structure + story summary from a pre-built prompt.

        This is the primary entry point when used with Agent 0's
        ``parseAndPrepareScenarios`` workflow.

        Parameters
        ----------
        prompt : str
            Complete prompt built by Agent 0 (already contains all params,
            context, and instructions).

        Returns
        -------
        dict
            Structure dict with keys: scenario_id, titre_global,
            resumeHistoire, structure, arc_emotionnel_global, etc.
        """
        logger.info("Creating structure from pre-built prompt")

        try:
            response = self.client.create_message(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                system=self.system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            response_text = response.content[0].text
            structure = self._extract_json(response_text)

            # Ensure resumeHistoire exists
            if "resumeHistoire" not in structure:
                structure["resumeHistoire"] = (
                    structure.get("titre_global", "Scénario historique")
                )
                logger.warning(
                    "resumeHistoire missing from LLM response — "
                    "falling back to titre_global"
                )

            logger.info(
                "Structure created: %s | resume: %s...",
                structure.get("titre_global", "N/A"),
                structure.get("resumeHistoire", "")[:80],
            )
            return structure

        except Exception as e:
            logger.error("Error in createStructureFromPrompt: %s", e, exc_info=True)
            return self._create_fallback_structure(
                scenario_id=1, duree=120, axe="mixte"
            )

    # ==================================================================
    # Legacy: create_narrative_structure (backward compat)
    # ==================================================================

    def create_narrative_structure(
        self,
        config: Dict[str, Any],
        scenario_num: int,
        audio_metadata: Optional[List] = None,
    ) -> Dict[str, Any]:
        """Create complete narrative structure for a scenario (legacy path).

        Kept for backward compatibility. In the new pipeline,
        ``createStructureFromPrompt`` is preferred.
        """
        logger.info("Creating narrative structure for scenario %d", scenario_num)

        gen_params = config.get("scenario_config", {}).get(
            "generation_parameters", {}
        )
        hist_context = config.get("scenario_config", {}).get(
            "historical_context", {}
        )

        duree = gen_params.get("duree", {}).get("value", 120)
        forme = gen_params.get("forme", {}).get("value", "documentaire")
        ton = gen_params.get("ton", {}).get("value", "neutre_informatif")
        public = gen_params.get("public_cible", {}).get("value", "grand_public")
        axe = gen_params.get("axe_narratif", {}).get("value", "mixte")
        structure_type = gen_params.get("structure_narrative", {}).get(
            "value", "chronologique"
        )
        rythme = gen_params.get("rythme", {}).get("value", "modere")
        angle_scenarisation = gen_params.get("angle_scenarisation", {}).get(
            "value", "auto"
        )
        original_prompt = (
            config.get("scenario_config", {})
            .get("user_input", {})
            .get("original_prompt", "")
        )

        if axe == "mixte":
            distribution = gen_params.get("axe_narratif", {}).get(
                "distribution", {}
            )
            axe = distribution.get(f"scenario_{scenario_num}", "travailleur")

        emotional_arc = self.define_emotional_arc(
            ton, structure_type, duree, public
        )

        audio_section = ""
        if audio_metadata:
            audio_lines = []
            for t in audio_metadata:
                name = t.get("file_name", "audio")
                text = t.get("transcription", "")
                if text:
                    audio_lines.append(f"- {name}: {text[:300]}...")
            if audio_lines:
                audio_section = (
                    "\n\nARCHIVES AUDIO DISPONIBLES :\n"
                    + "\n".join(audio_lines)
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
        angle_desc = angle_descriptions.get(angle_scenarisation, "")
        angle_line = ""
        if angle_desc:
            angle_line = (
                f"\n- Angle de scénarisation : {angle_scenarisation}"
                f"\n  → {angle_desc}"
            )

        prompt_section = ""
        if original_prompt and original_prompt.strip():
            prompt_section = (
                f'\n\nDEMANDE ORIGINALE :\n"{original_prompt.strip()}"'
                "\n→ Respectez les intentions ci-dessus."
            )

        user_requirements_block = build_user_requirement_block(config)
        mission_priority = ""
        if user_requirements_block:
            mission_priority = (
                "\n7. PRIORITÉ ABSOLUE : respecte le brief utilisateur."
            )

        prompt = f"""Créez une structure narrative + résumé d'histoire pour un scénario audio historique.

{(user_requirements_block + chr(10) + chr(10)) if user_requirements_block else ''}PARAMÈTRES :
- Durée totale : {duree}s
- Forme : {forme}
- Ton : {ton}
- Public : {public}
- Axe narratif : {axe}
- Structure : {structure_type}
- Rythme : {rythme}
- Perspective : {gen_params.get('perspective_narrative', {{}}).get('value', 'troisieme_personne')}{angle_line}
{prompt_section}

CONTEXTE HISTORIQUE :
- Période : {hist_context.get('period', {{}}).get('start_year', 'N/A')}-{hist_context.get('period', {{}}).get('end_year', 'N/A')}
- Lieu : {hist_context.get('location', {{}}).get('primary', 'Non spécifié')}
- Thèmes : {', '.join(hist_context.get('themes', {{}}).get('primary', []))}
{audio_section}

ARC ÉMOTIONNEL : {emotional_arc}

MISSION :
1. Décidez du nombre de sections (1-7) librement.
2. Durées ≈ {duree}s (± 10 %%).
3. Pour chaque section : titre, durée, fonction, arc émotionnel, éléments, mood.
4. Transitions clés (fluidité).
5. Notes de production.
6. L'angle « {angle_scenarisation} » définit la manière de raconter.{mission_priority}
8. IMPORTANT — Rédigez un « resumeHistoire » : résumé narratif de 3-5 phrases.

Retournez un JSON :
{{
  "scenario_id": {scenario_num},
  "titre_global": "Titre captivant",
  "resumeHistoire": "Résumé narratif 3-5 phrases...",
  "axe_narratif": "{axe}",
  "angle_scenarisation": "{angle_scenarisation}",
  "duree_totale": {duree},
  "structure": [
    {{
      "partie": 1,
      "titre": "Titre section",
      "duree_cible": 60.0,
      "fonction_narrative": "exposition",
      "position_arc_emotionnel": "calme",
      "elements_necessaires": ["elem1"],
      "mood": "descriptif"
    }}
  ],
  "arc_emotionnel_global": "{emotional_arc['type']}",
  "rythme_general": "{rythme}",
  "transitions_cles": [
    {{
      "entre_parties": [1, 2],
      "type": "progression_naturelle",
      "duree": 2.0,
      "description": "Description"
    }}
  ],
  "notes_production": "Instructions fluidité..."
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
            structure = self._extract_json(response_text)

            if "resumeHistoire" not in structure:
                structure["resumeHistoire"] = structure.get(
                    "titre_global", "Scénario historique"
                )

            logger.info(
                "Structure created: %s", structure.get("titre_global", "N/A")
            )
            return structure

        except Exception as e:
            logger.error("Error creating structure: %s", e, exc_info=True)
            return self._create_fallback_structure(scenario_num, duree, axe)

    # ==================================================================
    # Helpers
    # ==================================================================

    def calculate_parts_distribution(
        self,
        total_duration: int,
        public_cible: str,
        rythme: str,
        structure_type: str,
    ) -> List[float]:
        if total_duration <= 90:
            num_parts = 2
        elif total_duration <= 180:
            num_parts = 3
        elif total_duration <= 360:
            num_parts = 4
        else:
            num_parts = 5

        if public_cible in ["enfants", "scolaire_primaire"]:
            num_parts = max(num_parts, int(total_duration / 50))

        if structure_type == "crescendo_emotionnel":
            return self._crescendo_distribution(total_duration, num_parts)
        elif structure_type == "flashback" and num_parts == 3:
            return [
                total_duration * 0.2,
                total_duration * 0.6,
                total_duration * 0.2,
            ]
        return self._balanced_distribution(total_duration, num_parts)

    def define_emotional_arc(
        self, tone: str, structure_type: str, duration: float, public_cible: str
    ) -> Dict[str, Any]:
        if tone in ["dramatique_immersif", "emotionnel_personnel"]:
            arc_type = "progression_crescendo"
        elif tone == "contemplatif_poetique":
            arc_type = "contemplative"
        elif structure_type == "circulaire":
            arc_type = "circulaire"
        else:
            arc_type = "tension_resolution"

        arcs = {
            "progression_crescendo": [
                {"position": 0.0, "etat": "calme", "intensite": 0.2},
                {"position": 0.4, "etat": "tension_montante", "intensite": 0.5},
                {"position": 0.75, "etat": "climax", "intensite": 0.9},
                {"position": 1.0, "etat": "resolution", "intensite": 0.4},
            ],
            "contemplative": [
                {"position": 0.0, "etat": "calme", "intensite": 0.3},
                {"position": 0.5, "etat": "reflection", "intensite": 0.5},
                {"position": 1.0, "etat": "contemplation", "intensite": 0.4},
            ],
            "circulaire": [
                {"position": 0.0, "etat": "debut", "intensite": 0.3},
                {"position": 0.3, "etat": "exploration", "intensite": 0.6},
                {"position": 0.7, "etat": "revelation", "intensite": 0.8},
                {"position": 1.0, "etat": "retour_transforme", "intensite": 0.3},
            ],
            "tension_resolution": [
                {"position": 0.0, "etat": "setup", "intensite": 0.3},
                {"position": 0.2, "etat": "tension", "intensite": 0.7},
                {"position": 0.6, "etat": "climax", "intensite": 0.9},
                {"position": 1.0, "etat": "resolution", "intensite": 0.3},
            ],
        }
        return {"type": arc_type, "points_cles": arcs.get(arc_type, arcs["tension_resolution"])}

    def _balanced_distribution(self, total: float, num_parts: int) -> List[float]:
        base = total / num_parts
        return [base] * num_parts

    def _crescendo_distribution(self, total: float, num_parts: int) -> List[float]:
        weights = [1 + (i * 0.5) for i in range(num_parts)]
        total_weight = sum(weights)
        return [(w / total_weight) * total for w in weights]

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
        raise ValueError("Could not extract valid JSON from response")

    def _create_fallback_structure(
        self,
        scenario_id: int,
        duree: float,
        axe: str,
        parts_durations: Optional[List[float]] = None,
    ) -> Dict:
        logger.warning("Creating fallback structure")
        if duree <= 120:
            parts_durations = [duree * 0.4, duree * 0.6]
            functions = ["exposition", "développement"]
            moods = ["calme", "intense"]
        else:
            parts_durations = [duree * 0.25, duree * 0.50, duree * 0.25]
            functions = ["exposition", "développement", "résolution"]
            moods = ["calme", "intense", "apaisement"]

        structure = [
            {
                "partie": i + 1,
                "titre": f"Section {i + 1}",
                "duree_cible": parts_durations[i],
                "fonction_narrative": functions[i],
                "position_arc_emotionnel": moods[i],
                "elements_necessaires": ["contexte", "action", "transition"],
                "mood": moods[i],
            }
            for i in range(len(parts_durations))
        ]

        return {
            "scenario_id": scenario_id,
            "titre_global": "Scénario historique",
            "resumeHistoire": "Un récit explorant un épisode historique du territoire.",
            "axe_narratif": axe,
            "duree_totale": duree,
            "structure": structure,
            "arc_emotionnel_global": "progression_crescendo",
            "rythme_general": "modere",
            "transitions_cles": [],
            "notes_production": "Structure générée automatiquement — fluidité narrative",
        }
