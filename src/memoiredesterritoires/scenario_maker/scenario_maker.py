"""Skill wrapper that triggers the Mémoire des Territoires orchestrator."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from orchestrator import ScenarioMakerOrchestrator


class ScenarioMakerSkill:
    """
    High-level skill used by the main agent to generate scenarios.

    The skill wraps the ScenarioMakerOrchestrator described in ``agents.md`` and exposes a
    lightweight interface that accepts a prompt (simple mode) or a ready-to-use configuration
    (expert mode). It optionally injects user-provided audio transcripts into the configuration
    before invoking the orchestrator so downstream agents can rely on authentic archival sources.
    """

    def __init__(
        self,
        default_config_path: Union[str, Path] = "config/default_config.json",
        default_output_dir: Union[str, Path] = "./output",
    ) -> None:
        self.default_config_path = Path(default_config_path)
        self.default_output_dir = Path(default_output_dir)
        self.logger = logging.getLogger(self.__class__.__name__)

    def __call__(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Enable ``skill(params)`` shorthand."""
        return self.run(params)

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate one or more scenarios using the Mémoire des Territoires orchestrator.

        Expected params:
            prompt (str): natural language request when ``mode == "simple"``.
            mode (str): "simple" (default) or "expert".
            config_path (str): optional path to the base configuration JSON.
            output_dir (str): where orchestrator outputs must be persisted.
            audio_transcriptions (Sequence[dict|tuple]): optional transcripts linked to audio files.
            expert_config (dict|str): overrides for expert mode (dict or JSON file path).
            api_key (str): optional Anthropic key; falls back to env variables otherwise.
            log_level (str): orchestrator log level (defaults to "INFO").
            persist_updated_config (bool): when True, rewritten config is saved next to output_dir.
            updated_config_path (str): optional explicit path for the rewritten config file.

        Returns:
            Dict[str, Any]: Orchestrator result enriched with helper metadata.
        """
        mode = str(params.get("mode", "simple")).lower()
        prompt = params.get("prompt")
        config_path = Path(params.get("config_path", self.default_config_path))
        output_dir = Path(params.get("output_dir", self.default_output_dir))
        self.logger.info("ScenarioMakerSkill run (mode=%s, output_dir=%s)", mode, output_dir)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            raise PermissionError(f"Cannot create output directory: {output_dir}") from exc

        audio_transcriptions = self._normalize_audio_transcriptions(
            params.get("audio_transcriptions") or []
        )
        config_data = self._load_config(config_path)
        scenario_target = params.get("scenario_target")
        forced_scenario_target: Optional[int] = None
        if isinstance(scenario_target, int):
            forced_scenario_target = scenario_target
            scenario_config = config_data.setdefault("scenario_config", {})
            gen_params = scenario_config.setdefault("generation_parameters", {})
            nombre = gen_params.setdefault("nombre_scenarios", {})
            nombre["value"] = scenario_target
            nombre["user_specified"] = True
        if audio_transcriptions:
            self._inject_audio_transcriptions(config_data, audio_transcriptions)

        # Resolve the LLM model to use (e.g. "opus" → "anthropic/claude-opus-4-5")
        model_id = params.get("model_id")

        orchestrator = ScenarioMakerOrchestrator(
            config_path=str(config_path),
            api_key=params.get("api_key"),
            log_level=params.get("log_level", "INFO"),
            model_id=model_id,
            scenario_target_override=forced_scenario_target,
        )

        # Ensure orchestrator uses the possibly enriched configuration.
        orchestrator.default_config = config_data

        user_input = self._prepare_user_input(
            mode=mode,
            prompt=prompt,
            params=params,
            fallback_config=config_data,
        )

        result = orchestrator.create_scenarios(
            user_input=user_input,
            mode=mode,
            output_dir=str(output_dir),
        )

        # Optionally persist the updated configuration for traceability/debugging.
        persist = params.get("persist_updated_config", False)
        updated_config_path = params.get("updated_config_path")
        if persist or updated_config_path:
            path = Path(updated_config_path) if updated_config_path else output_dir / "config_used.json"
            self._save_json(path, config_data)

        result_meta = {
            "status": result.get("status", "error"),
            "output_dir": str(output_dir),
            "config_path": str(config_path),
            "scenario_count": len(result.get("scenarios", [])),
        }
        result["skill_metadata"] = result_meta
        return result

    def _prepare_user_input(
        self,
        mode: str,
        prompt: Optional[str],
        params: Dict[str, Any],
        fallback_config: Dict[str, Any],
    ) -> Union[str, Dict[str, Any]]:
        """Validate inputs and prepare the payload expected by Agent 0."""
        if mode == "simple":
            if not prompt:
                raise ValueError("ScenarioMakerSkill requires a 'prompt' when mode is 'simple'.")
            return prompt

        if mode == "expert":
            expert_config = params.get("expert_config")
            expert_config_path = params.get("expert_config_path")

            if isinstance(expert_config, dict):
                return expert_config

            if isinstance(expert_config, str):
                return self._load_config(Path(expert_config))

            if expert_config_path:
                return self._load_config(Path(expert_config_path))

            return fallback_config

        raise ValueError(f"Unsupported mode '{mode}'. Use 'simple' or 'expert'.")

    def _load_config(self, path: Path) -> Dict[str, Any]:
        """Load JSON config from disk."""
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Serialize data to JSON with UTF-8 encoding."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _inject_audio_transcriptions(
        self,
        config: Dict[str, Any],
        audio_transcriptions: List[Dict[str, Any]],
    ) -> None:
        """Insert normalized transcripts under user_provided sources."""
        scenario_config = config.setdefault("scenario_config", {})
        data_sources = scenario_config.setdefault("data_sources", {})
        user_provided = data_sources.setdefault("user_provided", {})
        user_provided["audio_transcriptions"] = audio_transcriptions

    def _normalize_audio_transcriptions(
        self,
        audio_transcriptions: Sequence[Any],
    ) -> List[Dict[str, Any]]:
        """Normalize free-form transcript inputs into the expected schema."""
        normalized: List[Dict[str, Any]] = []
        for entry in audio_transcriptions:
            if isinstance(entry, dict):
                file_name = entry.get("file_name") or entry.get("name")
                transcription = entry.get("transcription") or entry.get("text")
                if not file_name or not transcription:
                    continue
                normalized.append(
                    {
                        "file_name": file_name,
                        "transcription": transcription,
                        "language": entry.get("language", "fr"),
                        "notes": entry.get("notes"),
                        "source": entry.get("source"),
                    }
                )
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                file_name, transcription = entry[0], entry[1]
                normalized.append(
                    {
                        "file_name": str(file_name),
                        "transcription": str(transcription),
                        "language": "fr",
                        "notes": None,
                        "source": None,
                    }
                )
        return normalized
