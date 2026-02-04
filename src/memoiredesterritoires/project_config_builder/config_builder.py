"""Skill that adapts the default scenario configuration for a specific project."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from agents.agent_0_request_parser import RequestParserAgent
from utils.claude_client import ClaudeClient


class ScenarioConfigBuilderSkill:
    """
    Build a project-specific scenario configuration JSON.

    This skill consumes a textual description of the upcoming project along with any
    supplementary resources (documents, audio transcriptions, etc.), merges them into the
    default configuration, and writes a ready-to-use JSON file that can be passed to the
    ScenarioMaker skill or CLI in expert mode.
    """

    def __init__(
        self,
        default_config_path: Union[str, Path] = "config/default_config.json",
        default_output_dir: Union[str, Path] = "./output/configs",
    ) -> None:
        self.default_config_path = Path(default_config_path)
        self.default_output_dir = Path(default_output_dir)
        self.logger = logging.getLogger(self.__class__.__name__)

    def __call__(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.run(params)

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a tailored configuration from textual instructions.

        Expected params:
            project_description (str): Narrative description of the new project (simple mode).
            mode (str): "simple" (default) or "expert".
            project_config (dict|str): Expert configuration override (dict or path).
            base_config_path (str): Path to the default config JSON.
            output_path (str): Where to save the adapted configuration.
            audio_transcriptions (Sequence[dict|tuple]): transcripts to inject.
            documents (Sequence[str|dict]): optional textual sources to attach.
            project_name (str): to overwrite metadata.project_name.
            api_key (str): Anthropic API key or rely on ANTHROPIC_API_KEY env variable.
        """
        mode = str(params.get("mode", "simple")).lower()
        project_description = params.get("project_description") or params.get("prompt")
        base_config_path = Path(params.get("base_config_path", self.default_config_path))
        output_path = Path(
            params.get(
                "output_path",
                self.default_output_dir / "project_scenario_config.json",
            )
        )

        config_data = self._load_config(base_config_path)
        transcripts = self._normalize_audio_transcriptions(params.get("audio_transcriptions") or [])
        documents = self._normalize_documents(params.get("documents") or [])

        if transcripts:
            self._inject_audio_transcriptions(config_data, transcripts)
        if documents:
            self._inject_documents(config_data, documents)

        self._apply_project_metadata(config_data, params)

        updated_config = self._build_config_with_agent(
            mode=mode,
            description=project_description,
            params=params,
            base_config=config_data,
        )

        if transcripts:
            self._inject_audio_transcriptions(updated_config, transcripts)
        if documents:
            self._inject_documents(updated_config, documents)
        self._apply_project_metadata(updated_config, params)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._save_json(output_path, updated_config)

        return {
            "status": "success",
            "config_path": str(output_path),
            "config": updated_config,
        }

    def _build_config_with_agent(
        self,
        mode: str,
        description: Optional[str],
        params: Dict[str, Any],
        base_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Leverage Agent 0 to parse the project instructions."""
        api_key = params.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ScenarioConfigBuilderSkill requires an Anthropic API key.")

        client = ClaudeClient(api_key=api_key)
        parser_agent = RequestParserAgent(client)

        if mode == "simple":
            if not description:
                raise ValueError("project_description is required when mode is 'simple'.")
            return parser_agent.parse(description, mode, base_config)

        if mode == "expert":
            expert_config = params.get("project_config")
            expert_config_path = params.get("project_config_path")
            if isinstance(expert_config, dict):
                return parser_agent.parse(expert_config, mode, base_config)
            if isinstance(expert_config, str):
                data = self._load_config(Path(expert_config))
                return parser_agent.parse(data, mode, base_config)
            if expert_config_path:
                data = self._load_config(Path(expert_config_path))
                return parser_agent.parse(data, mode, base_config)
            # fall back to base config directly
            return parser_agent.parse(base_config, mode, base_config)

        raise ValueError(f"Unsupported mode '{mode}'. Use 'simple' or 'expert'.")

    def _load_config(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_json(self, path: Path, data: Dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _apply_project_metadata(self, config: Dict[str, Any], params: Dict[str, Any]) -> None:
        project_name = params.get("project_name")
        user_mode = params.get("mode")
        metadata = config.setdefault("scenario_config", {}).setdefault("metadata", {})
        if project_name:
            metadata["project_name"] = project_name
        if user_mode:
            metadata["user_mode"] = user_mode

    def _inject_audio_transcriptions(
        self,
        config: Dict[str, Any],
        transcripts: List[Dict[str, Any]],
    ) -> None:
        scenario_config = config.setdefault("scenario_config", {})
        data_sources = scenario_config.setdefault("data_sources", {})
        user_provided = data_sources.setdefault("user_provided", {})
        user_provided["audio_transcriptions"] = transcripts

    def _inject_documents(
        self,
        config: Dict[str, Any],
        documents: List[Dict[str, Any]],
    ) -> None:
        scenario_config = config.setdefault("scenario_config", {})
        data_sources = scenario_config.setdefault("data_sources", {})
        user_provided = data_sources.setdefault("user_provided", {})
        user_provided["documents"] = documents

    def _normalize_audio_transcriptions(
        self,
        audio_transcriptions: Sequence[Any],
    ) -> List[Dict[str, Any]]:
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

    def _normalize_documents(self, documents: Sequence[Any]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for doc in documents:
            if isinstance(doc, dict):
                content = doc.get("content") or doc.get("text")
                if not content:
                    continue
                normalized.append(
                    {
                        "title": doc.get("title", "Document"),
                        "content": content,
                        "source": doc.get("source"),
                    }
                )
            elif isinstance(doc, str):
                normalized.append(
                    {
                        "title": "Document",
                        "content": doc,
                        "source": None,
                    }
                )
        return normalized
