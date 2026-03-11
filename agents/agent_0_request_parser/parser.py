"""
Agent 0: Request Parser & Config Builder
Parses user requests, builds configuration, and generates prompt templates
for Agent 1 (structure) and Agent 2 (writing).
"""

import json
import logging
import random
from typing import Dict, Any, Union, List, Optional
from copy import deepcopy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants for scenario variation
# ---------------------------------------------------------------------------

ANGLE_POOL = [
    "temoignage_croise",
    "chronique_sociale",
    "journee_type",
    "portrait_individuel",
    "avant_apres_evenement",
    "mosaique_voix",
    "lettre_intime",
    "recit_initiatique",
]

SOFT_VARIABILITY_PARAMS = [
    "ton",
    "structure_narrative",
    "perspective_narrative",
    "forme",
    "rythme",
    "densite_sonore",
    "epoque_linguistique",
    "niveau_detail_historique",
    "axe_narratif",
]

ANGLE_DESCRIPTIONS: Dict[str, str] = {
    "temoignage_croise": (
        "Récit à la 1ère personne avec plusieurs témoins qui se relaient. "
        "Chaque voix apporte un regard différent sur le même vécu."
    ),
    "chronique_sociale": (
        "Chronique à la 3ème personne racontant la vie d'un groupe social, "
        "ses habitudes, son quotidien, ses luttes."
    ),
    "journee_type": (
        "Une journée type racontée du matin au soir — rythme ancré dans "
        "le concret des gestes et des heures."
    ),
    "portrait_individuel": (
        "Portrait intime d'un individu, son parcours, ses pensées, "
        "son évolution au fil du récit."
    ),
    "avant_apres_evenement": (
        "Structure en diptyque : la vie avant un événement marquant, "
        "puis la transformation après."
    ),
    "mosaique_voix": (
        "Fragments de voix, de souvenirs et de témoignages entrelacés "
        "comme un collage sonore."
    ),
    "lettre_intime": (
        "Sous forme de lettre ou de journal intime — ton confidentiel "
        "et personnel."
    ),
    "recit_initiatique": (
        "Parcours d'apprentissage ou de découverte — le narrateur entre "
        "dans un monde inconnu et le comprend peu à peu."
    ),
}


class RequestParserAgent:
    """Agent 0: Parses requests, builds config, and generates prompt templates."""

    def __init__(self, client):
        self.client = client
        self.model = "claude-sonnet-4-5"
        self.temperature = 0.1
        self.max_tokens = 6000

        self.system_prompt = (
            "Vous êtes un expert en analyse de besoins pour la création de "
            "contenus audio historiques. Votre rôle est d'extraire avec "
            "précision tous les paramètres nécessaires depuis une demande "
            "utilisateur.\n\n"
            "Règles strictes :\n"
            "1. Extrayez UNIQUEMENT les informations explicitement mentionnées "
            "ou fortement impliquées\n"
            "2. Marquez clairement ce qui est spécifié par l'utilisateur vs "
            "valeur par défaut\n"
            "3. Assurez la cohérence : ajustez automatiquement les "
            "incompatibilités\n"
            "4. Retournez TOUJOURS un JSON valide et complet\n"
            "5. Soyez précis sur les dates, durées, lieux et thématiques "
            "historiques"
        )

        logger.info("RequestParserAgent initialized")

    # ==================================================================
    # Main entry point (NEW)
    # ==================================================================

    def parseAndPrepareScenarios(
        self,
        userInput: Union[str, Dict],
        mode: str,
        defaultConfig: Dict[str, Any],
        audioTranscriptions: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Full Agent 0 pipeline: parse, vary per scenario, generate prompts.

        Returns
        -------
        dict with keys:
            config           – base config (with options, for reference)
            scenarioPrompts  – list of per-scenario prompt bundles
        """
        # 1. Parse user input (existing logic)
        config = self.parse(userInput, mode, defaultConfig)

        # Store original prompt
        userInputSection = (
            config.setdefault("scenario_config", {})
            .setdefault("user_input", {})
        )
        if isinstance(userInput, str):
            userInputSection["original_prompt"] = userInput
        else:
            userInputSection["original_prompt"] = userInput.get("prompt", "")

        # 2. Determine number of scenarios
        numScenarios = (
            config.get("scenario_config", {})
            .get("generation_parameters", {})
            .get("nombre_scenarios", {})
            .get("value", 3)
        )

        # 3. For each scenario: vary → clean → generate prompts
        usedValues: Dict[str, List[str]] = {}
        scenarioPrompts: List[Dict[str, Any]] = []

        for i in range(numScenarios):
            variedConfig = self._varyConfigForScenario(config, i + 1, usedValues)
            cleanedConfig = self._cleanConfigForPrompt(variedConfig)

            # Collect varied param values for metadata
            gp = cleanedConfig.get("scenario_config", {}).get(
                "generation_parameters", {}
            )
            variedParams = {
                k: (v.get("value") if isinstance(v, dict) else v)
                for k, v in gp.items()
            }

            prompts = self._generatePromptTemplates(
                cleanedConfig, i + 1, audioTranscriptions or []
            )

            scenarioPrompts.append(
                {
                    "scenarioNum": i + 1,
                    "variedParams": variedParams,
                    "promptAgent1": prompts["promptAgent1"],
                    "promptTemplateAgent2": prompts["promptTemplateAgent2"],
                }
            )

        logger.info(
            "Agent 0 prepared %d scenario prompt sets", len(scenarioPrompts)
        )
        return {"config": config, "scenarioPrompts": scenarioPrompts}

    # ==================================================================
    # Existing parse methods (preserved)
    # ==================================================================

    def parse(
        self,
        user_input: Union[str, Dict],
        mode: str,
        default_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Route to simple or expert mode."""
        logger.info("Parsing request in %s mode", mode)
        if mode == "simple":
            return self.parse_simple_prompt(str(user_input), default_config)
        elif mode == "expert":
            return self.merge_expert_config(dict(user_input), default_config)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def parse_simple_prompt(
        self, user_prompt: str, default_config: Dict
    ) -> Dict:
        """Parse a simple natural language prompt."""
        logger.info("Parsing simple prompt: %s...", user_prompt[:100])

        prompt = (
            "Analysez cette demande et extrayez TOUS les paramètres pour "
            "générer des archives audio historiques.\n\n"
            f"DEMANDE UTILISATEUR :\n{user_prompt}\n\n"
            "CONFIGURATION PAR DÉFAUT (référence) :\n"
            f"{json.dumps(default_config.get('scenario_config', {}).get('generation_parameters', {}), indent=2, ensure_ascii=False)}\n\n"
            "INSTRUCTIONS :\n"
            "1. Identifiez la forme narrative\n"
            "2. Extrayez la durée (en secondes)\n"
            "3. Déterminez le ton approprié\n"
            "4. Identifiez le public cible\n"
            "5. Extrayez période historique, lieux, thématiques\n\n"
            "RÈGLE CRITIQUE pour user_specified :\n"
            "- true UNIQUEMENT pour les paramètres EXPLICITEMENT mentionnés\n"
            "- false pour tout ce qui est déduit ou laissé par défaut\n"
            "- JAMAIS true sur angle_scenarisation\n\n"
            "Retournez un JSON :\n"
            "{\n"
            '  "generation_parameters": {\n'
            '    "forme": {"value": "...", "user_specified": true/false},\n'
            '    "duree": {"value": 120, "user_specified": true/false},\n'
            '    "ton": {"value": "...", "user_specified": true/false},\n'
            '    "public_cible": {"value": "...", "user_specified": true/false}\n'
            "  },\n"
            '  "historical_context": {\n'
            '    "period": {"start_year": ..., "end_year": ...},\n'
            '    "location": {"primary": "...", "specific_areas": [...]},\n'
            '    "themes": {"primary": [...], "secondary": [...]}\n'
            "  }\n"
            "}\n\nJSON :"
        )

        try:
            response = self.client.create_message(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                system=self.system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            response_text = response.content[0].text
            extracted = self._extract_json(response_text)
            config = self._merge_configs(extracted, default_config)

            # Preserve audio transcriptions
            default_data_sources = (
                default_config.get("scenario_config", {}).get("data_sources", {})
            )
            if default_data_sources:
                sc = config.setdefault("scenario_config", {})
                sc["data_sources"] = deepcopy(default_data_sources)
                audio_t = (
                    config.get("scenario_config", {})
                    .get("data_sources", {})
                    .get("user_provided", {})
                    .get("audio_transcriptions", [])
                )
                logger.info("Audio transcriptions preserved: %d", len(audio_t))

            config = self._validate_and_adjust(config)
            logger.info("Simple prompt parsed successfully")
            return config

        except Exception as e:
            logger.error("Error parsing simple prompt: %s", e, exc_info=True)
            logger.warning("Falling back to default configuration")
            return deepcopy(default_config)

    def merge_expert_config(
        self, user_config: Dict, default_config: Dict
    ) -> Dict:
        """Merge expert configuration with defaults."""
        logger.info("Merging expert configuration")
        config = deepcopy(default_config)
        config = self._deep_merge(config, user_config)

        if "data_sources" not in user_config.get("scenario_config", {}):
            default_ds = default_config.get("scenario_config", {}).get(
                "data_sources", {}
            )
            if default_ds:
                sc = config.setdefault("scenario_config", {})
                sc.setdefault("data_sources", {})
                if "user_provided" not in user_config.get(
                    "scenario_config", {}
                ).get("data_sources", {}):
                    sc["data_sources"]["user_provided"] = deepcopy(
                        default_ds.get("user_provided", {})
                    )

        self._mark_user_specified(config, user_config)
        config = self._validate_and_adjust(config)
        logger.info("Expert config merged successfully")
        return config

    # ==================================================================
    # Validation & summary (preserved)
    # ==================================================================

    def validate_configuration(self, config: Dict) -> Dict[str, Any]:
        """Validate configuration and return errors/warnings."""
        errors: List[str] = []
        warnings: List[str] = []
        gen_params = config.get("scenario_config", {}).get(
            "generation_parameters", {}
        )

        duree = gen_params.get("duree", {}).get("value", 120)
        if duree < 60:
            warnings.append(f"Durée très courte: {duree}s. Recommandé: 120s minimum")
        elif duree > 600:
            warnings.append(f"Durée très longue: {duree}s. Considérez diviser en épisodes")

        public = gen_params.get("public_cible", {}).get("value", "")
        ton = gen_params.get("ton", {}).get("value", "")
        if public in ["enfants", "scolaire_primaire"]:
            if ton in ["dramatique_immersif", "emotionnel_personnel"]:
                warnings.append(
                    f"Ton '{ton}' peut être trop intense pour '{public}'."
                )

        balance = gen_params.get("equilibre_narration_archives", {}).get("value", 0.6)
        if balance < 0.3:
            warnings.append("Équilibre faible : trop d'archives")
        elif balance > 0.9:
            warnings.append("Équilibre élevé : sous-utilisation des archives")

        ds = config.get("scenario_config", {}).get("data_sources", {})
        up = ds.get("user_provided", {})
        audio_t = up.get("audio_transcriptions", [])
        audio_f = up.get("audio_files", [])
        if audio_f and not audio_t:
            warnings.append(
                f"{len(audio_f)} fichiers audio uploadés mais 0 transcriptions."
            )
        if audio_t:
            logger.info("%d transcriptions audio disponibles", len(audio_t))

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def generate_summary(self, config: Dict) -> str:
        """Generate human-readable summary of configuration."""
        gp = config.get("scenario_config", {}).get("generation_parameters", {})
        hc = config.get("scenario_config", {}).get("historical_context", {})

        parts = ["=== Configuration Générée ===\n", "Paramètres principaux:"]
        parts.append(f"  - Forme: {gp.get('forme', {}).get('value', 'N/A')}")
        parts.append(f"  - Durée: {gp.get('duree', {}).get('value', 'N/A')}s")
        parts.append(f"  - Ton: {gp.get('ton', {}).get('value', 'N/A')}")
        parts.append(f"  - Public: {gp.get('public_cible', {}).get('value', 'N/A')}")
        parts.append(f"  - Scénarios: {gp.get('nombre_scenarios', {}).get('value', 3)}")

        period = hc.get("period", {})
        if period.get("start_year"):
            parts.append("\nContexte historique:")
            parts.append(f"  - Période: {period.get('start_year')}-{period.get('end_year')}")
            loc = hc.get("location", {})
            if loc.get("primary"):
                parts.append(f"  - Lieu: {loc['primary']}")
            themes = hc.get("themes", {})
            if themes.get("primary"):
                parts.append(f"  - Thèmes: {', '.join(themes['primary'])}")

        user_specified = [
            k for k, v in gp.items()
            if isinstance(v, dict) and v.get("user_specified")
        ]
        if user_specified:
            parts.append(
                f"\nParamètres spécifiés: {', '.join(user_specified)}"
            )
        return "\n".join(parts)

    # ==================================================================
    # Config cleaning (NEW)
    # ==================================================================

    def _cleanConfigForPrompt(self, config: Dict) -> Dict:
        """Strip options / default / note / range / details from
        generation_parameters so the prompts are lean and readable."""
        cleaned = deepcopy(config)
        gp = cleaned.get("scenario_config", {}).get("generation_parameters", {})
        keysToStrip = ["options", "default", "note", "range", "details"]
        for _paramName, paramData in gp.items():
            if isinstance(paramData, dict):
                for key in keysToStrip:
                    paramData.pop(key, None)
        return cleaned

    # ==================================================================
    # Variation logic (moved from orchestrator)
    # ==================================================================

    def _varyConfigForScenario(
        self,
        baseConfig: Dict,
        scenarioNum: int,
        usedValues: Dict[str, List[str]],
    ) -> Dict:
        """Return a deep copy with unique angle_scenarisation and soft
        variation on non-user-specified parameters."""
        config = deepcopy(baseConfig)
        gp = config.get("scenario_config", {}).get("generation_parameters", {})
        changed: List[str] = []

        # 1. Unique angle
        angleParam = gp.get("angle_scenarisation")
        if isinstance(angleParam, dict):
            already = usedValues.get("angle_scenarisation", [])
            remaining = [a for a in ANGLE_POOL if a not in already]
            if not remaining:
                remaining = list(ANGLE_POOL)
            chosen = random.choice(remaining)
            angleParam["value"] = chosen
            already.append(chosen)
            usedValues["angle_scenarisation"] = already
            changed.append(f"angle_scenarisation={chosen}")

        # 2. Soft variation
        for paramKey in SOFT_VARIABILITY_PARAMS:
            param = gp.get(paramKey)
            if not isinstance(param, dict):
                continue
            if param.get("user_specified", False):
                continue
            options = param.get("options")
            if not options or not isinstance(options, list) or len(options) < 2:
                continue
            already = usedValues.get(paramKey, [])
            candidates = [v for v in options if v not in already]
            if not candidates:
                candidates = list(options)
            chosen = random.choice(candidates)
            param["value"] = chosen
            already.append(chosen)
            usedValues[paramKey] = already
            changed.append(f"{paramKey}={chosen}")

        logger.info(
            "[Variation] Scenario %d — %d params changed: %s",
            scenarioNum,
            len(changed),
            ", ".join(changed) if changed else "(none)",
        )
        return config

    # ==================================================================
    # Prompt template generation (NEW)
    # ==================================================================

    def _buildParamsBlock(
        self, config: Dict, audioTranscriptions: List[Dict]
    ) -> str:
        """Build a comprehensive text block with ALL config params."""
        gp = config.get("scenario_config", {}).get("generation_parameters", {})
        hc = config.get("scenario_config", {}).get("historical_context", {})
        originalPrompt = (
            config.get("scenario_config", {})
            .get("user_input", {})
            .get("original_prompt", "")
        )
        voiceInstructions = config.get("voice_instructions") or config.get(
            "scenario_config", {}
        ).get("voice_instructions", "")

        def _val(key: str) -> Any:
            entry = gp.get(key, {})
            return entry.get("value", "") if isinstance(entry, dict) else entry

        angle = _val("angle_scenarisation")
        angleDesc = ANGLE_DESCRIPTIONS.get(str(angle), "")
        angleLine = f"- Angle de scénarisation : {angle}"
        if angleDesc:
            angleLine += f"\n  → {angleDesc}"

        lines: List[str] = [
            "=== PARAMÈTRES DE GÉNÉRATION ===",
            f"- Forme narrative : {_val('forme')}",
            f"- Durée cible : {_val('duree')} secondes",
            f"- Ton : {_val('ton')}",
            f"- Public cible : {_val('public_cible')}",
            f"- Axe narratif : {_val('axe_narratif')}",
            f"- Structure narrative : {_val('structure_narrative')}",
            f"- Rythme : {_val('rythme')}",
            f"- Perspective narrative : {_val('perspective_narrative')}",
            angleLine,
            f"- Époque linguistique : {_val('epoque_linguistique')}",
            f"- Densité sonore : {_val('densite_sonore')}",
            f"- Niveau de détail historique : {_val('niveau_detail_historique')}",
            f"- Équilibre narration/archives : {_val('equilibre_narration_archives')}",
            f"- Authenticité vs accessibilité : {_val('authenticite_vs_accessibilite')}",
        ]

        # Historical context
        period = hc.get("period", {})
        location = hc.get("location", {})
        themes = hc.get("themes", {})

        lines += [
            "",
            "=== CONTEXTE HISTORIQUE ===",
            f"- Période : {period.get('start_year', 'N/A')}-{period.get('end_year', 'N/A')}",
            f"- Lieu principal : {location.get('primary', 'Non spécifié')}",
        ]
        if location.get("specific_areas"):
            lines.append(
                f"- Zones spécifiques : {', '.join(location['specific_areas'])}"
            )
        if themes.get("primary"):
            lines.append(
                f"- Thèmes principaux : {', '.join(themes['primary'])}"
            )
        if themes.get("secondary"):
            lines.append(
                f"- Thèmes secondaires : {', '.join(themes['secondary'])}"
            )
        if hc.get("key_events"):
            lines.append(
                f"- Événements clés : {', '.join(str(e) for e in hc['key_events'])}"
            )
        if hc.get("key_figures"):
            lines.append(
                f"- Personnages clés : {', '.join(str(f) for f in hc['key_figures'])}"
            )

        # Audio transcriptions
        if audioTranscriptions:
            lines += ["", "=== ARCHIVES AUDIO DISPONIBLES (transcriptions) ==="]
            for t in audioTranscriptions:
                name = t.get("file_name", "audio")
                text = t.get("transcription", "")
                if text:
                    lines.append(f"--- {name} ---")
                    lines.append(text[:3000])

        # Voice instructions
        if voiceInstructions:
            lines += [
                "",
                "=== CONSIGNES VOCALES DE L'UTILISATEUR ===",
                str(voiceInstructions),
            ]

        # Original user prompt
        if originalPrompt and originalPrompt.strip():
            lines += [
                "",
                "=== DEMANDE ORIGINALE DE L'UTILISATEUR ===",
                f'"{originalPrompt.strip()}"',
                "→ Respectez scrupuleusement les intentions et souhaits ci-dessus.",
            ]

        # Locked params
        locked = [
            k for k, v in gp.items()
            if isinstance(v, dict) and v.get("user_specified")
        ]
        if locked:
            lines += [
                "",
                "=== PARAMÈTRES VERROUILLÉS PAR L'UTILISATEUR ===",
                ", ".join(locked),
            ]

        return "\n".join(lines)

    def _generatePromptTemplates(
        self,
        config: Dict,
        scenarioNum: int,
        audioTranscriptions: List[Dict],
    ) -> Dict[str, str]:
        """Generate prompt templates for Agent 1 and Agent 2."""
        paramsBlock = self._buildParamsBlock(config, audioTranscriptions)
        gp = config.get("scenario_config", {}).get("generation_parameters", {})
        duree = gp.get("duree", {}).get("value", 120)
        angle = gp.get("angle_scenarisation", {}).get("value", "auto")

        # ---- Prompt Agent 1 (Structure + Résumé) ----
        promptAgent1 = (
            f"Créez une structure narrative ET un résumé d'histoire pour le "
            f"scénario audio historique #{scenarioNum}.\n\n"
            f"{paramsBlock}\n\n"
            "=== VOTRE MISSION (Agent 1 — Architecte Narratif) ===\n"
            "1. Concevez la structure narrative en décidant librement du nombre "
            "de sections (1 à 7) selon ce qui est NATUREL pour ce récit.\n"
            f"2. La somme des durées ≈ {duree}s (± 10 %%).\n"
            "3. Pour chaque section : titre, durée cible, fonction narrative, "
            "position sur l'arc émotionnel, éléments nécessaires, mood.\n"
            f"4. L'angle « {angle} » définit la MANIÈRE de raconter — "
            "structurez les sections pour le servir.\n"
            "5. Définissez les transitions clés (fluidité > rupture).\n"
            "6. Ajoutez des notes de production sur la CONTINUITÉ narrative.\n"
            "7. IMPORTANT — Rédigez un « resumeHistoire » : résumé narratif "
            "de 3 à 5 phrases décrivant l'histoire qui sera écrite. Ce résumé "
            "doit poser le décor, les personnages/situations et l'arc "
            "dramatique.\n\n"
            "RIGUEUR HISTORIQUE :\n"
            "- N'INVENTEZ JAMAIS de dates, noms, lieux ou événements absents "
            "du contexte.\n"
            "- Si le contexte est insuffisant → formulations vagues.\n\n"
            "Retournez un JSON EXACT :\n"
            "{\n"
            f'  "scenario_id": {scenarioNum},\n'
            '  "titre_global": "Titre captivant",\n'
            '  "resumeHistoire": "Résumé narratif 3-5 phrases...",\n'
            '  "axe_narratif": "...",\n'
            f'  "angle_scenarisation": "{angle}",\n'
            f'  "duree_totale": {duree},\n'
            '  "structure": [\n'
            "    {\n"
            '      "partie": 1,\n'
            '      "titre": "Titre section",\n'
            '      "duree_cible": 60.0,\n'
            '      "fonction_narrative": "exposition",\n'
            '      "position_arc_emotionnel": "calme",\n'
            '      "elements_necessaires": ["elem1", "elem2"],\n'
            '      "mood": "descriptif"\n'
            "    }\n"
            "  ],\n"
            '  "arc_emotionnel_global": "type_arc",\n'
            '  "rythme_general": "...",\n'
            '  "transitions_cles": [\n'
            "    {\n"
            '      "entre_parties": [1, 2],\n'
            '      "type": "progression_naturelle",\n'
            '      "duree": 2.0,\n'
            '      "description": "Description"\n'
            "    }\n"
            "  ],\n"
            '  "notes_production": "Instructions fluidité..."\n'
            "}\n\n"
            "JSON :"
        )

        # ---- Prompt Template Agent 2 (Writing) ----
        # <<STRUCTURE_ET_RESUME>> will be replaced at runtime with Agent 1 output
        promptTemplateAgent2 = (
            f"Écrivez le scénario audio historique complet #{scenarioNum}.\n\n"
            f"{paramsBlock}\n\n"
            "=== STRUCTURE NARRATIVE ET RÉSUMÉ (fournis par l'architecte) ===\n"
            "<<STRUCTURE_ET_RESUME>>\n\n"
            "=== VOTRE MISSION (Agent 2 — Scénariste Historique) ===\n"
            "1. Écrivez le texte narratif complet pour TOUTES les parties en "
            "une seule réponse cohérente et FLUIDE.\n"
            "2. Le récit doit être CONTINU — les parties sont des repères de "
            "rythme, pas des coupures.\n"
            f"3. L'angle « {angle} » définit la MANIÈRE de raconter — "
            "suivez-le fidèlement.\n"
            "4. Adaptez le vocabulaire au public cible et à l'époque.\n"
            "5. Si des transcriptions audio sont fournies, UTILISEZ-LES : "
            "intégrez les mots et témoignages réels.\n"
            "6. Pour chaque partie : 2-3 moments clés + directions de ton.\n"
            "7. Respectez strictement les durées cibles (~2.5 mots/seconde).\n\n"
            "RIGUEUR HISTORIQUE (non négociable) :\n"
            "- EXCLUSIVEMENT basé sur le contexte et transcriptions fournis.\n"
            "- N'INVENTEZ JAMAIS de dates, noms, lieux ou événements absents "
            "des sources.\n\n"
            "Retournez un JSON :\n"
            "{\n"
            '  "parties": [\n'
            "    {\n"
            '      "partie_id": 1,\n'
            '      "titre": "...",\n'
            '      "duree": 45.0,\n'
            '      "texte_narration": "Le texte narratif complet...",\n'
            '      "ton": {\n'
            '        "global": "...",\n'
            '        "tempo_lecture": 110,\n'
            '        "pauses": ["après tel mot (2s)"],\n'
            '        "intonation": "..."\n'
            "      },\n"
            '      "moments_cles": [\n'
            '        {"timestamp": "0:XX", "action": "...", "duree": 2.0}\n'
            "      ],\n"
            '      "ambiances_continues": []\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "JSON :"
        )

        return {
            "promptAgent1": promptAgent1,
            "promptTemplateAgent2": promptTemplateAgent2,
        }

    # ==================================================================
    # Internal helpers (preserved)
    # ==================================================================

    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from Claude response."""
        import re

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError("Could not extract valid JSON from response")

    def _merge_configs(self, extracted: Dict, default: Dict) -> Dict:
        result = deepcopy(default)
        return self._deep_merge(result, {"scenario_config": extracted})

    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def _mark_user_specified(
        self, config: Dict, user_config: Dict, prefix: str = ""
    ):
        for key, value in user_config.items():
            if isinstance(value, dict):
                if "value" in value:
                    if key in config:
                        config[key]["user_specified"] = True
                else:
                    if key in config:
                        self._mark_user_specified(
                            config[key], value, f"{prefix}.{key}"
                        )

    def _validate_and_adjust(self, config: Dict) -> Dict:
        gp = config.get("scenario_config", {}).get("generation_parameters", {})
        public = gp.get("public_cible", {}).get("value")
        ton = gp.get("ton", {}).get("value")
        if public in ["enfants", "scolaire_primaire"]:
            if ton in ["dramatique_immersif", "emotionnel_personnel"]:
                logger.info("Auto-adjusting tone for children")
                gp["ton"]["value"] = "pedagogique_accessible"
                gp["ton"]["user_specified"] = False
        return config

    def _generate_axe_distribution(self, nombre_scenarios: int) -> Dict[str, str]:
        axes = [
            "travailleur",
            "objet_lieu",
            "evenement_historique",
            "contexte_social",
        ]
        return {
            f"scenario_{i + 1}": axes[i % len(axes)]
            for i in range(nombre_scenarios)
        }
