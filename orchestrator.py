"""
Main orchestrator for Mémoire des Territoires.
Coordinates all agents and skills for scenario generation.
Supports parallel execution of scenario chains via ThreadPoolExecutor.
"""

import os
import json
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Dict, Any, Union, List, Optional
from datetime import datetime

from utils.claude_client import ClaudeClient
from utils.logger import setup_logger, AgentLogger
from utils.skill_loader import SkillLoader

logger = logging.getLogger(__name__)


class ScenarioMakerOrchestrator:
    """Main orchestrator that coordinates all agents and skills."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        api_key: Optional[str] = None,
        log_level: str = "INFO",
        model_id: Optional[str] = None,
        scenario_target_override: Optional[int] = None,
        tts_provider: str = "elevenlabs",
    ):
        # Setup logging
        log_file = os.getenv("LOG_FILE", "./logs/memoire_territoires.log")
        self.logger = setup_logger(
            name="memoire_territoires", level=log_level, log_file=log_file
        )

        logger.info("=" * 80)
        logger.info("Initializing Mémoire des Territoires Orchestrator")
        logger.info("=" * 80)

        self.model_id = model_id
        if model_id:
            logger.info("Model override: %s", model_id)

        # TTS provider — Agent 3 only runs when elevenlabs is selected
        self.tts_provider = (tts_provider or "elevenlabs").lower()
        logger.info("TTS provider: %s", self.tts_provider)

        # Scenario target override (slider)
        self.scenario_target_override: Optional[int] = None
        if scenario_target_override is not None:
            try:
                forced = int(scenario_target_override)
                if forced < 1:
                    raise ValueError
                self.scenario_target_override = forced
                logger.info("Scenario target override active: %d", forced)
            except Exception:
                logger.warning(
                    "Ignoring invalid scenario_target_override=%r",
                    scenario_target_override,
                )

        # Claude client
        try:
            self.client = ClaudeClient(api_key=api_key)
            logger.info("Claude client initialized (OpenRouter)")
        except Exception as e:
            logger.error("Failed to initialize Claude client: %s", e)
            raise

        # Load default configuration
        self.config_path = config_path or "config/default_config.json"
        self.default_config = self._load_config(self.config_path)
        logger.info("Loaded configuration from %s", self.config_path)

        # Load agents and skills
        self.agents: Dict[str, Any] = {}
        self.skills: Dict[str, Any] = {}
        self._load_all_skills()

        if self.model_id:
            self._apply_model_override(self.model_id)

        logger.info("Orchestrator initialization complete")
        logger.info(
            "Loaded %d agents, %d skills", len(self.agents), len(self.skills)
        )

    # ==================================================================
    # Config & setup
    # ==================================================================

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        path = Path(config_path)
        if not path.exists():
            logger.warning("Config file not found: %s", config_path)
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Error loading config: %s", e)
            return {}

    def _load_all_skills(self):
        agents_dir = Path("agents")
        if agents_dir.exists():
            logger.info("Loading agents...")
            self.agents = SkillLoader.load_all_skills(
                agents_dir, self.client, skill_type="agents"
            )
            logger.info(
                "Loaded %d agents: %s", len(self.agents), list(self.agents.keys())
            )
        else:
            logger.warning("Agents directory not found")

        skills_dir = Path("skills")
        if skills_dir.exists():
            logger.info("Loading skills...")
            self.skills = SkillLoader.load_all_skills(
                skills_dir, self.client, skill_type="skills"
            )
            logger.info(
                "Loaded %d skills: %s", len(self.skills), list(self.skills.keys())
            )
        else:
            logger.warning("Skills directory not found")

    def _apply_model_override(self, model_id: str):
        for name, data in self.agents.items():
            inst = data.get("instance")
            if inst and hasattr(inst, "model"):
                old = getattr(inst, "model", None)
                inst.model = model_id
                logger.info("Model override [%s]: %s → %s", name, old, model_id)
        for name, data in self.skills.items():
            inst = data.get("instance")
            if inst and hasattr(inst, "model"):
                old = getattr(inst, "model", None)
                inst.model = model_id
                logger.info("Model override [%s]: %s → %s", name, old, model_id)

    def _apply_scenario_target_override(self, config: Dict[str, Any]) -> None:
        if self.scenario_target_override is None:
            return
        forced = self.scenario_target_override
        sc = config.setdefault("scenario_config", {})
        gp = sc.setdefault("generation_parameters", {})
        nombre = gp.setdefault("nombre_scenarios", {})
        prev = nombre.get("value")
        nombre["value"] = forced
        nombre["user_specified"] = True
        nombre["source"] = "project_slider"
        sc.setdefault("metadata", {})["scenario_target_override"] = forced
        if prev != forced:
            logger.info("Scenario count override: %s → %s", prev, forced)

    # ==================================================================
    # Main pipeline (NEW — parallel)
    # ==================================================================

    def create_scenarios(
        self,
        user_input: Union[str, Dict],
        mode: str = "simple",
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Full pipeline v3: Agent 0 → parallel (Agent 1 → 2 → 3) chains.

        Parameters
        ----------
        user_input : str or dict
            User prompt (simple) or expert config (dict).
        mode : str
            ``"simple"`` or ``"expert"``.
        output_dir : str, optional
            Directory to save outputs.

        Returns
        -------
        dict with config, scenarios, generation_time, status.
        """
        logger.info("=" * 80)
        logger.info("Starting PARALLEL scenario generation pipeline (mode: %s)", mode)
        logger.info("=" * 80)

        start_time = datetime.now()

        try:
            # ----------------------------------------------------------
            # Step 1: Agent 0 — parse + prepare scenario prompts
            # ----------------------------------------------------------
            agent0 = self._get_agent("agent_0_request_parser")
            a0_logger = AgentLogger("Agent 0")

            # Get audio transcriptions from default config
            audio_transcriptions = self._extract_audio_transcriptions(
                self.default_config
            )

            a0_logger.log_start("Parse request + prepare scenario prompts")

            # Apply scenario target override to default config before parsing
            default_cfg = deepcopy(self.default_config)
            self._apply_scenario_target_override(default_cfg)

            a0_output = agent0.parseAndPrepareScenarios(
                userInput=user_input,
                mode=mode,
                defaultConfig=default_cfg,
                audioTranscriptions=audio_transcriptions,
            )
            a0_logger.log_end("Parse + prepare", status="success")

            config = a0_output["config"]
            scenarioPrompts = a0_output["scenarioPrompts"]

            # Enforce scenario target override on the resulting config too
            self._apply_scenario_target_override(config)

            # Validate
            validation = agent0.validate_configuration(config)
            for w in validation.get("warnings", []):
                logger.warning("Config: %s", w)
            if not validation["valid"]:
                raise ValueError(f"Configuration invalid: {validation['errors']}")

            logger.info(
                "Agent 0 produced %d scenario prompts", len(scenarioPrompts)
            )

            # ----------------------------------------------------------
            # Step 2: Run scenario chains in parallel
            # ----------------------------------------------------------
            scenarios_complete: List[Dict[str, Any]] = [None] * len(
                scenarioPrompts
            )

            max_workers = min(len(scenarioPrompts), 5)
            logger.info(
                "Launching %d parallel chains (max_workers=%d)",
                len(scenarioPrompts),
                max_workers,
            )

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_idx = {}
                for idx, sp in enumerate(scenarioPrompts):
                    future = executor.submit(
                        self._runScenarioChain,
                        sp,
                        config,
                    )
                    future_to_idx[future] = idx

                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    snum = scenarioPrompts[idx]["scenarioNum"]
                    try:
                        result = future.result()
                        scenarios_complete[idx] = result
                        logger.info("✓ Scenario %d completed", snum)
                    except Exception as e:
                        logger.error(
                            "✗ Scenario %d failed: %s", snum, e, exc_info=True
                        )
                        scenarios_complete[idx] = {
                            "error": str(e),
                            "scenario_id": snum,
                        }

            # ----------------------------------------------------------
            # Step 3: Build result
            # ----------------------------------------------------------
            result = {
                "config": config,
                "scenarios": scenarios_complete,
                "generation_time": (
                    datetime.now() - start_time
                ).total_seconds(),
                "status": "success",
                "message": (
                    f"Pipeline completed: {len(scenarios_complete)} scenarios"
                ),
            }

            if output_dir:
                self._save_complete_outputs(result, output_dir)

            logger.info("=" * 80)
            logger.info(
                "PARALLEL PIPELINE completed in %.2fs", result["generation_time"]
            )
            logger.info("Generated %d scenarios", len(scenarios_complete))
            logger.info("=" * 80)

            return result

        except Exception as e:
            logger.error("Pipeline error: %s", e, exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "generation_time": (
                    datetime.now() - start_time
                ).total_seconds(),
            }

    # ==================================================================
    # Single scenario chain (Agent 1 → 2 → 3)
    # ==================================================================

    def _runScenarioChain(
        self,
        scenarioPrompt: Dict[str, Any],
        baseConfig: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the full chain for ONE scenario (thread-safe).

        Parameters
        ----------
        scenarioPrompt : dict
            One entry from Agent 0's scenarioPrompts list.
        baseConfig : dict
            Base config (for skills injection, etc.).

        Returns
        -------
        dict with structure, scenario, taggedOutput.
        """
        snum = scenarioPrompt["scenarioNum"]
        promptAgent1 = scenarioPrompt["promptAgent1"]
        promptTemplateAgent2 = scenarioPrompt["promptTemplateAgent2"]

        logger.info("[Chain %d] Starting Agent 1 → 2 → 3", snum)

        # ---- Agent 1: Structure + Resume ----
        agent1 = self._get_agent("agent_1_structure")
        a1_logger = AgentLogger(f"Agent 1 (#{snum})")
        a1_logger.log_start("Create structure from prompt")
        structure = agent1.createStructureFromPrompt(promptAgent1)
        a1_logger.log_end("Structure", status="success")

        logger.info(
            "[Chain %d] Agent 1 done — %s / resume: %s...",
            snum,
            structure.get("titre_global", "?"),
            structure.get("resumeHistoire", "")[:60],
        )

        # ---- Agent 2: Writing ----
        agent2 = self._get_agent("agent_2_writing")
        agent2.set_skills(self.skills)

        a2_logger = AgentLogger(f"Agent 2 (#{snum})")
        a2_logger.log_start("Write scenario from template")
        scenario = agent2.writeFromPromptTemplate(
            promptTemplateAgent2, structure
        )
        a2_logger.log_end("Writing", status="success")

        logger.info(
            "[Chain %d] Agent 2 done — %d words, %.1fs",
            snum,
            scenario.get("metadata", {}).get("nombre_mots", 0),
            scenario.get("duree_estimee", 0),
        )

        # ---- Agent 3: ElevenLabs tagging (only when provider is elevenlabs) ----
        taggedOutput = None
        if self.tts_provider == "elevenlabs":
            agent3 = self._get_agent("agent_3_production")
            agent3.set_skills(self.skills)

            a3_logger = AgentLogger(f"Agent 3 (#{snum})")
            a3_logger.log_start("Format with ElevenLabs tags")
            taggedOutput = agent3.formatWithTags(scenario, baseConfig)
            a3_logger.log_end("Tagging", status="success")

            logger.info(
                "[Chain %d] Agent 3 done — %d voice tags, %d sound tags",
                snum,
                taggedOutput.get("metadata", {}).get("voiceTags", 0),
                taggedOutput.get("metadata", {}).get("soundTags", 0),
            )
        else:
            logger.info(
                "[Chain %d] Agent 3 skipped (tts_provider=%s, not elevenlabs)",
                snum,
                self.tts_provider,
            )

        return {
            "structure": structure,
            "scenario": scenario,
            "taggedOutput": taggedOutput,
        }

    # ==================================================================
    # Helper: get agent instance
    # ==================================================================

    def _get_agent(self, agent_key: str):
        """Return the agent instance or raise if not loaded."""
        if agent_key not in self.agents:
            raise ValueError(f"Agent '{agent_key}' not loaded")
        return self.agents[agent_key]["instance"]

    # ==================================================================
    # Legacy run methods (backward compat)
    # ==================================================================

    def _run_agent_0(self, user_input: Union[str, Dict], mode: str) -> Dict:
        """Run Agent 0: Request Parser (legacy sequential path)."""
        agent_0 = self._get_agent("agent_0_request_parser")
        a0_logger = AgentLogger("Agent 0")
        a0_logger.log_start("Parse request and build configuration")
        config = agent_0.parse(user_input, mode, self.default_config)
        a0_logger.log_end("Parse request", status="success")
        self._apply_scenario_target_override(config)
        validation = agent_0.validate_configuration(config)
        for w in validation.get("warnings", []):
            logger.warning("Config: %s", w)
        if not validation["valid"]:
            raise ValueError(f"Configuration invalid: {validation['errors']}")
        return config

    def _run_agent_1(self, config: Dict, scenario_num: int) -> Dict:
        agent_1 = self._get_agent("agent_1_structure")
        audio_transcriptions = self._extract_audio_transcriptions(config)
        a1_logger = AgentLogger("Agent 1")
        a1_logger.log_start(f"Create structure #{scenario_num}")
        structure = agent_1.create_narrative_structure(
            config, scenario_num, audio_metadata=audio_transcriptions
        )
        a1_logger.log_end("Create structure", status="success")
        return structure

    def _run_agent_2(self, structure: Dict, config: Dict) -> Dict:
        agent_2 = self._get_agent("agent_2_writing")
        agent_2.set_skills(self.skills)
        audio_transcriptions = self._extract_audio_transcriptions(config)
        a2_logger = AgentLogger("Agent 2")
        a2_logger.log_start("Write complete scenario")
        scenario = agent_2.write_complete_scenario(
            structure, config, audio_transcriptions=audio_transcriptions
        )
        a2_logger.log_end("Write scenario", status="success")
        return scenario

    def _run_agent_3(self, scenario: Dict, config: Dict) -> Dict:
        agent_3 = self._get_agent("agent_3_production")
        agent_3.set_skills(self.skills)
        a3_logger = AgentLogger("Agent 3")
        a3_logger.log_start("Create audio timeline")
        timeline = agent_3.create_audio_timeline(scenario, None, config)
        a3_logger.log_end("Create timeline", status="success")
        return timeline

    # ==================================================================
    # Variation logic (legacy — kept for backward compat, now in Agent 0)
    # ==================================================================

    _ANGLE_POOL = [
        "temoignage_croise",
        "chronique_sociale",
        "journee_type",
        "portrait_individuel",
        "avant_apres_evenement",
    ]

    _SOFT_VARIABILITY_PARAMS = [
        "structure_narrative",
        "rythme",
        "densite_sonore",
        "niveau_detail_historique",
    ]

    def _vary_config_for_scenario(
        self,
        base_config: Dict,
        scenario_num: int,
        used_values: Dict[str, List[str]],
    ) -> Dict:
        """Legacy variation logic (now in Agent 0)."""
        config = deepcopy(base_config)
        gp = config.get("scenario_config", {}).get("generation_parameters", {})
        changed: List[str] = []

        angle_param = gp.get("angle_scenarisation")
        if isinstance(angle_param, dict):
            already = used_values.get("angle_scenarisation", [])
            remaining = [a for a in self._ANGLE_POOL if a not in already]
            if not remaining:
                remaining = list(self._ANGLE_POOL)
            chosen = random.choice(remaining)
            angle_param["value"] = chosen
            already.append(chosen)
            used_values["angle_scenarisation"] = already
            changed.append(f"angle_scenarisation={chosen}")

        for pk in self._SOFT_VARIABILITY_PARAMS:
            p = gp.get(pk)
            if not isinstance(p, dict) or p.get("user_specified", False):
                continue
            opts = p.get("options")
            if not opts or not isinstance(opts, list) or len(opts) < 2:
                continue
            already = used_values.get(pk, [])
            cands = [v for v in opts if v not in already]
            if not cands:
                cands = list(opts)
            chosen = random.choice(cands)
            p["value"] = chosen
            already.append(chosen)
            used_values[pk] = already
            changed.append(f"{pk}={chosen}")

        logger.info(
            "[Variation] Scenario %d — %d changed: %s",
            scenario_num,
            len(changed),
            ", ".join(changed) if changed else "(none)",
        )
        return config

    # ==================================================================
    # Output & utilities
    # ==================================================================

    def _extract_audio_transcriptions(self, config: Dict) -> List[Dict[str, Any]]:
        try:
            ds = config.get("scenario_config", {}).get("data_sources", {})
            up = ds.get("user_provided", {})
            transcriptions = up.get("audio_transcriptions") or []
            if isinstance(transcriptions, list):
                return [t for t in transcriptions if isinstance(t, dict)]
        except Exception as exc:
            logger.warning("Failed to extract audio transcriptions: %s", exc)
        return []

    def _save_complete_outputs(self, result: Dict, output_dir: str):
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save config
        cfg_file = output_path / "scenarios" / f"config_{ts}.json"
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(result["config"], f, indent=2, ensure_ascii=False)
        logger.info("[Agent 0] Config saved to %s", cfg_file)

        for i, sd in enumerate(result.get("scenarios", [])):
            if "error" in sd:
                continue

            # Structure
            if "structure" in sd:
                sf = output_path / "structures" / f"structure_{i+1}_{ts}.json"
                sf.parent.mkdir(parents=True, exist_ok=True)
                with open(sf, "w", encoding="utf-8") as f:
                    json.dump(sd["structure"], f, indent=2, ensure_ascii=False)
                logger.info("[Agent 1] Structure #%d saved to %s", i + 1, sf)

            # Scenario
            if "scenario" in sd:
                scf = output_path / "scenarios" / f"scenario_{i+1}_{ts}.json"
                with open(scf, "w", encoding="utf-8") as f:
                    json.dump(sd["scenario"], f, indent=2, ensure_ascii=False)
                logger.info("[Agent 2] Scenario #%d saved to %s", i + 1, scf)

            # Tagged output (Agent 3)
            if "taggedOutput" in sd:
                tof = output_path / "tagged" / f"tagged_{i+1}_{ts}.json"
                tof.parent.mkdir(parents=True, exist_ok=True)
                with open(tof, "w", encoding="utf-8") as f:
                    json.dump(
                        sd["taggedOutput"], f, indent=2, ensure_ascii=False
                    )
                logger.info("[Agent 3] Tagged output #%d saved to %s", i + 1, tof)

                # Also save the raw tagged text for easy review
                txt_file = output_path / "tagged" / f"tagged_{i+1}_{ts}.txt"
                with open(txt_file, "w", encoding="utf-8") as f:
                    f.write(sd["taggedOutput"].get("taggedText", ""))
                logger.info("[Agent 3] Tagged text #%d saved to %s", i + 1, txt_file)

            # Legacy timeline (if present)
            if "timeline" in sd:
                tlf = output_path / "timelines" / f"timeline_{i+1}_{ts}.json"
                tlf.parent.mkdir(parents=True, exist_ok=True)
                with open(tlf, "w", encoding="utf-8") as f:
                    json.dump(sd["timeline"], f, indent=2, ensure_ascii=False)
                logger.info("[Agent 3] Timeline #%d saved to %s", i + 1, tlf)

        logger.info("All outputs saved to %s", output_dir)

    def _save_output(self, result: Dict, output_dir: str):
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        of = output_path / f"config_{ts}.json"
        try:
            with open(of, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info("Output saved to %s", of)
        except Exception as e:
            logger.error("Error saving output: %s", e)

    def list_available_skills(self) -> Dict[str, List[str]]:
        return {
            "agents": list(self.agents.keys()),
            "skills": list(self.skills.keys()),
        }

    def get_skill_info(self, skill_name: str) -> Optional[Dict]:
        if skill_name in self.agents:
            return self.agents[skill_name]["config"]
        if skill_name in self.skills:
            return self.skills[skill_name]["config"]
        return None
