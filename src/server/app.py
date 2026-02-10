"""FastAPI application exposing the Mémoire des Territoires toolchain."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Query, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

from memoiredesterritoires.scenario_maker import ScenarioMakerSkill
from memoiredesterritoires.background_sound_finder.background_sound_finder import find_background_sounds
from memoiredesterritoires.text_to_speech_with_instructions.text_to_speech_with_instructions import (
    text_to_speech_with_instructions,
)
from memoiredesterritoires.transcription.transcription import transcribe_audio
from memoiredesterritoires.analysis_storage.analysis_storage import save_analysis_result, fetch_analysis_results
from project_store import (
    load_project_settings,
    save_project_settings,
    load_audio_selection,
    save_audio_selection,
    list_project_audio_files,
)

from .config import AppSettings, get_settings
from .session_store import SessionStore
from .step_config import StepConfigRegistry
from .automation import AutomationRunner
from .chat_agent import ChatAgent
from .audio_validation import validate_audio_file

logger = logging.getLogger(__name__)


def log_progress(event: str, **fields: Any) -> None:
    if not fields:
        logger.info(event)
        return
    details = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    logger.info("%s | %s", event, details)


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., description="Human readable project name")
    description: Optional[str] = Field(None, description="Optional blurb saved into project notes")
    scenario_target: int = Field(default=3, ge=1, le=5, description="Number of scenarios to generate")


class SessionCreateRequest(BaseModel):
    project_name: str
    initial_step: str = "project_selection"
    scenario_target: Optional[int] = Field(default=None, ge=1, le=5)


class StepTransitionRequest(BaseModel):
    step_id: str
    payload: dict = Field(default_factory=dict)


class ScenarioGenerationRequest(BaseModel):
    session_id: str
    prompt: str
    mode: str = "simple"
    output_dir: str = "./output"
    scenario_target: Optional[int] = Field(default=None, ge=1, le=5)


class ScenarioGenerationResponse(BaseModel):
    status: str
    scenario_count: int
    output_dir: str
    details: dict


class ScenarioSelectionPayload(BaseModel):
    scenario: Dict[str, Any]


class ScenarioSelectionResponse(BaseModel):
    scenario: Optional[Dict[str, Any]]


class AudioSelectionPayload(BaseModel):
    project_name: str
    voices: List[str] = Field(default_factory=list)
    backgrounds: List[str] = Field(default_factory=list)


class ScenarioAudioRequest(BaseModel):
    text: Optional[str] = None
    language: str = Field(default="French")


def create_app(settings: Optional[AppSettings] = None) -> FastAPI:
    settings = settings or get_settings()
    os.environ.setdefault("PROJECTS_DIR", str(settings.projects_dir))
    app = FastAPI(title="Mémoire des Territoires API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    step_registry = StepConfigRegistry(settings.step_config_path)
    session_store = SessionStore(settings.session_store)
    automation_runner = AutomationRunner(step_registry, settings)
    scenario_skill = ScenarioMakerSkill()
    chat_agent = ChatAgent()
    background_root = (Path.cwd() / settings.data_dir / "audio" / "background_sounds").resolve()

    def slugify(value: str) -> str:
        value = value.strip().lower()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        value = value.strip("-")
        return value or "ambiance"

    def resolve_background_path(path_value: str) -> Path:
        candidate = Path(path_value)
        if not candidate.is_absolute():
            candidate = (Path.cwd() / path_value).resolve()
        else:
            candidate = candidate.resolve()
        if background_root not in candidate.parents and candidate != background_root:
            raise HTTPException(status_code=400, detail="Chemin d'ambiance invalide")
        return candidate

    def extract_scenario_payload(entry: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(entry, dict):
            return {}
        scenario_payload = entry.get("scenario")
        if isinstance(scenario_payload, dict):
            return scenario_payload
        return entry

    def scenario_to_text(entry: Dict[str, Any]) -> str:
        payload = extract_scenario_payload(entry)
        if not payload:
            return ""
        chunks: List[str] = []
        title = payload.get("titre") or payload.get("title")
        if isinstance(title, str):
            chunks.append(title.strip())
        summary = payload.get("resume") or payload.get("texte") or payload.get("texte_narration")
        parties = payload.get("parties")
        if isinstance(parties, list) and parties:
            for part in parties:
                if not isinstance(part, dict):
                    continue
                part_lines = []
                if isinstance(part.get("titre"), str):
                    part_lines.append(part["titre"].strip())
                if isinstance(part.get("texte_narration"), str):
                    part_lines.append(part["texte_narration"].strip())
                elif isinstance(part.get("texte"), str):
                    part_lines.append(part["texte"].strip())
                if part_lines:
                    chunks.append("\n".join(part_lines))
        elif isinstance(summary, str):
            chunks.append(summary.strip())

        return "\n\n".join([chunk for chunk in chunks if chunk]).strip()

    def upsert_project_config_entry(project_name: str, updates: Dict[str, Any]) -> None:
        config_path = settings.config_json
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}

        entry = dict(config.get(project_name, {}))
        if "created_at" not in entry:
            entry["created_at"] = datetime.utcnow().isoformat()
        entry.setdefault("allowed_websites", ["wikipedia.org"])
        entry.setdefault("voice_instructions", "")
        for key, value in updates.items():
            if value is not None:
                entry[key] = value
        config[project_name] = entry
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def load_project_profile(project_name: str) -> Dict[str, Any]:
        config_path = settings.config_json
        if not config_path.exists():
            return {}
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return dict(config.get(project_name, {}))

    def build_voice_instruction_prompt(project_name: str, scenario_text: str) -> str:
        profile = load_project_profile(project_name)
        sections: List[str] = []
        if profile.get("project_notes"):
            sections.append(f"Brief projet : {profile['project_notes']}")
        if profile.get("tone"):
            sections.append(f"Ton souhaité : {profile['tone']}")
        if profile.get("audience"):
            sections.append(f"Public ciblé : {profile['audience']}")
        if profile.get("scenario_target"):
            sections.append(f"Nombre de scénarios générés : {profile['scenario_target']}")
        if profile.get("allowed_websites"):
            sections.append(f"Références autorisées : {', '.join(profile['allowed_websites'])}")
        sections.append("Texte actuel du scénario :")
        sections.append(scenario_text.strip())
        return "\n".join(sections)

    def ensure_voice_instructions(project_name: str, scenario_text: str, language_hint: str) -> str:
        profile = load_project_profile(project_name)
        existing = profile.get("voice_instructions")
        if isinstance(existing, str) and existing.strip():
            return existing

        notes = profile.get("project_notes") or "Documentaire historique sur le patrimoine maritime français."
        tone = profile.get("tone") or "narration immersive, empathique et documentée"
        audience = profile.get("audience") or "grand public"
        snippet = "\n".join(scenario_text.strip().split("\n")[:5])[:600]

        instructions = (
            f"Voice for project '{project_name}' ({audience}). Speak in {language_hint} with a {tone}. "
            f"Context: {notes}. Narrator should sound mature (45-60), grounded working-class French accent, "
            f"clear articulation, moderate tempo, gentle breaths, emotional lift on key sentences. "
            f"Scenario excerpt:\n{snippet}"
        )
        upsert_project_config_entry(project_name, {"voice_instructions": instructions})
        return instructions

    async def transcribe_and_store(project_name: str, audio_path: Path, meta: Optional[Dict[str, Any]] = None) -> None:
        meta = meta or {}
        loop = asyncio.get_running_loop()
        log_progress(
            "TRANSCRIPTION_START",
            project=project_name,
            file=audio_path.name,
        )

        def _run_transcription() -> str:
            return transcribe_audio(str(audio_path))

        try:
            transcript = await loop.run_in_executor(None, _run_transcription)
            save_analysis_result(
                analysis_type="transcription",
                source_path=str(audio_path),
                result={"transcription": transcript},
                title=audio_path.name,
                metadata={
                    "project": project_name,
                    "duration": meta.get("duration"),
                    "samplerate": meta.get("samplerate"),
                    "frames": meta.get("frames"),
                },
                is_partial=False,
            )
            log_progress(
                "TRANSCRIPTION_DONE",
                project=project_name,
                file=audio_path.name,
            )
        except Exception as exc:
            log_progress(
                "TRANSCRIPTION_FAILED",
                project=project_name,
                file=audio_path.name,
                error=str(exc),
            )
            raise

    def fetch_project_transcriptions(project_name: str) -> List[Dict[str, Any]]:
        """Retrieve stored transcriptions for a project from the Parquet dataset."""
        try:
            data = fetch_analysis_results(
                analysis_type="transcription",
                source_path_contains=project_name,
                limit=50,
            )
            transcriptions: List[Dict[str, Any]] = []
            for entry in data.get("entries", []):
                result = entry.get("result", {})
                text = result.get("transcription") if isinstance(result, dict) else None
                title = entry.get("title") or Path(entry.get("source_path", "")).name
                if text and title:
                    transcriptions.append({
                        "file_name": title,
                        "transcription": text,
                        "language": "fr",
                        "source": entry.get("source_path"),
                    })
            log_progress(
                "TRANSCRIPTIONS_FETCHED",
                project=project_name,
                count=len(transcriptions),
            )
            return transcriptions
        except Exception as exc:
            logger.warning("Could not fetch transcriptions for %s: %s", project_name, exc)
            return []

    def persist_final_assets(project_name: str, session_data: Dict[str, Any]) -> None:
        entry: Dict[str, Any] = {
            "finalized_at": datetime.utcnow().isoformat(),
        }
        if session_data.get("selected_scenario"):
            entry["final_scenario"] = session_data["selected_scenario"]
        audio_meta = session_data.get("scenario_audio")
        if audio_meta:
            entry["final_audio"] = audio_meta
        upsert_project_config_entry(project_name, entry)

    @app.get("/health", tags=["system"])
    async def health_check() -> dict:
        return {
            "status": "ok",
            "steps": len(step_registry.steps),
        }

    @app.get("/steps", tags=["config"])
    async def list_steps() -> dict:
        return {"steps": step_registry.steps}

    @app.get("/steps/{step_id}", tags=["config"])
    async def get_step(step_id: str) -> dict:
        step = step_registry.find_step(step_id)
        if not step:
            raise HTTPException(status_code=404, detail="Step not found")
        return step

    @app.post("/projects", tags=["projects"])
    async def create_project(payload: ProjectCreateRequest) -> dict:
        project_dir = settings.projects_dir / payload.name
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "audio").mkdir(exist_ok=True)
        (project_dir / "notes").mkdir(exist_ok=True)
        (project_dir / "outputs").mkdir(exist_ok=True)
        save_project_settings(payload.name, {"scenario_target": payload.scenario_target})
        upsert_project_config_entry(
            payload.name,
            {
                "project_notes": payload.description.strip() if payload.description else None,
                "scenario_target": payload.scenario_target,
            },
        )

        if payload.description:
            automation_runner.update_project_notes(payload.name, payload.description)
        log_progress(
            "PROJECT_CREATED",
            project=payload.name,
            scenario_target=payload.scenario_target,
        )

        return {
            "project": payload.name,
            "path": str(project_dir),
            "scenario_target": payload.scenario_target,
        }

    @app.get("/projects", tags=["projects"])
    async def list_projects() -> dict:
        projects: List[dict] = []
        if settings.projects_dir.exists():
            for child in sorted(settings.projects_dir.iterdir()):
                if child.is_dir():
                    meta = load_project_settings(child.name)
                    profile = load_project_profile(child.name)
                    projects.append({
                        "name": child.name,
                        "scenario_target": meta.get("scenario_target", 3),
                        "final_audio": profile.get("final_audio"),
                        "finalized_at": profile.get("finalized_at"),
                    })
        return {"projects": projects}

    @app.post("/sessions", tags=["sessions"])
    async def create_session(payload: SessionCreateRequest) -> dict:
        automation_runner.ensure_project_exists(payload.project_name)
        settings_meta = load_project_settings(payload.project_name)
        target = payload.scenario_target or settings_meta.get("scenario_target", 3)
        session = session_store.create_session(payload.project_name, payload.initial_step, scenario_target=target)
        log_progress(
            "SESSION_CREATED",
            session=session.get("id"),
            project=payload.project_name,
            initial_step=payload.initial_step,
            scenario_target=target,
        )
        return session

    @app.get("/sessions/{session_id}", tags=["sessions"])
    async def get_session(session_id: str) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    @app.post("/sessions/{session_id}/step", tags=["sessions"])
    async def advance_step(session_id: str, payload: StepTransitionRequest) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if payload.step_id == "audio_sources":
            files = payload.payload.get("files") if payload.payload else None
            if not files:
                raise HTTPException(status_code=400, detail="Sélectionnez au moins une piste audio avant de continuer")
        if payload.step_id == "scenario_edit" and not session.get("selected_scenario"):
            raise HTTPException(status_code=400, detail="Sélectionnez d'abord un scénario")
        if payload.step_id == "final_validation" and not session.get("selected_scenario"):
            raise HTTPException(status_code=400, detail="Aucun scénario sélectionné")
        if payload.step_id == "final_validation":
            persist_final_assets(session["project_name"], session)

        session_store.update_session(session_id, {
            "current_step": payload.step_id,
            "steps": {payload.step_id: payload.payload},
        })
        log_progress(
            "STEP_TRANSITION",
            session=session_id,
            project=session["project_name"],
            step=payload.step_id,
        )
        results = automation_runner.run(payload.step_id, session["project_name"], payload.payload)
        log_progress(
            "STEP_AUTOMATIONS_DONE",
            session=session_id,
            step=payload.step_id,
            automations=len(results or []),
        )
        return {"session_id": session_id, "step": payload.step_id, "automations": results}

    @app.post("/scenarios/generate", response_model=ScenarioGenerationResponse, tags=["scenarios"])
    async def generate_scenarios(req: ScenarioGenerationRequest):
        session = session_store.load_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        project_name = session["project_name"]
        selection = load_audio_selection(project_name)
        voices = selection.get("voices", [])
        backgrounds = selection.get("backgrounds", [])
        if not voices:
            raise HTTPException(status_code=400, detail="Aucune piste vocale sélectionnée pour ce projet.")
        progress_template = [
            {"label": "Préparation du projet", "message": "Chargement du brief et du paramétrage"},
            {"label": "Contrôle des sources audio", "message": "Vérification des pistes sélectionnées"},
            {"label": "Génération multi-agents", "message": "Agents 0 → 3 en cours"},
            {"label": "Consolidation finale", "message": "Sauvegarde des scénarios et mises à jour"},
        ]
        session_store.init_scenario_progress(req.session_id, progress_template)

        def mark(idx: int, status: str, message: Optional[str] = None) -> None:
            session_store.update_scenario_progress(req.session_id, idx, status, message)
            label = progress_template[idx]["label"] if 0 <= idx < len(progress_template) else f"Step-{idx}"
            log_progress(
                "SCENARIO_STAGE",
                session=req.session_id,
                project=project_name,
                stage=label,
                status=status,
                message=message,
            )

        current_step = 0

        def start_step(idx: int, message: str) -> None:
            nonlocal current_step
            current_step = idx
            mark(idx, "running", message)

        def finish_step(idx: int, message: str) -> None:
            mark(idx, "done", message)

        # Retrieve audio transcriptions from Parquet storage
        audio_transcriptions = fetch_project_transcriptions(project_name)

        # Load project notes and enrich the prompt
        project_profile = load_project_profile(project_name)
        project_notes = project_profile.get("project_notes", "")
        
        # Enrich prompt with project context if notes exist
        enriched_prompt = req.prompt
        if project_notes and project_notes.strip():
            if enriched_prompt and enriched_prompt.strip():
                enriched_prompt = f"{project_notes}\n\n{enriched_prompt}"
            else:
                enriched_prompt = project_notes

        params = {
            "prompt": enriched_prompt,
            "mode": req.mode,
            "output_dir": req.output_dir,
            "scenario_target": req.scenario_target or session.get("scenario_target", 3),
            "audio_transcriptions": audio_transcriptions,
        }
        log_progress(
            "SCENARIO_GENERATE_START",
            session=req.session_id,
            project=project_name,
            target=params["scenario_target"],
            transcriptions=len(audio_transcriptions),
        )
        try:
            start_step(0, "Analyse du prompt et lecture du brief projet")
            project_settings = load_project_settings(project_name)
            finish_step(
                0,
                f"Brief chargé (cible: {project_settings.get('scenario_target', 3)} scénarios)",
            )

            start_step(1, "Vérification des pistes vocales et ambiances")
            missing_files: List[str] = []
            audio_dir = settings.projects_dir / project_name / "audio"
            for voice_name in voices:
                if not (audio_dir / voice_name).exists():
                    missing_files.append(voice_name)
            for bg in backgrounds:
                bg_path = Path(bg)
                if not bg_path.is_absolute():
                    bg_path = (Path.cwd() / bg).resolve()
                if not bg_path.exists():
                    missing_files.append(bg)
            if missing_files:
                raise HTTPException(
                    status_code=400,
                    detail=f"Fichiers audio introuvables: {', '.join(missing_files)}",
                )
            finish_step(
                1,
                f"{len(voices)} piste(s) vocale(s) et {len(backgrounds)} ambiance(s) prêtes",
            )

            start_step(2, "Lancement des agents (0 → 3)")
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda: scenario_skill.run(params))
            scenario_count = result.get("skill_metadata", {}).get("scenario_count") or len(result.get("scenarios", []))
            finish_step(2, f"{scenario_count} scénario(s) généré(s)")

            # Save agent intermediate outputs for inspection
            agent_outputs = {
                "agent_0_config": result.get("config"),
                "scenarios": [],
            }
            for idx_out, sc_data in enumerate(result.get("scenarios", [])):
                if isinstance(sc_data, dict) and "error" not in sc_data:
                    agent_outputs["scenarios"].append({
                        "scenario_index": idx_out + 1,
                        "agent_1_structure": sc_data.get("structure"),
                        "agent_2_scenario": sc_data.get("scenario"),
                        "agent_3_timeline": sc_data.get("timeline"),
                    })
            session_store.save_agent_outputs(req.session_id, agent_outputs)

            start_step(3, "Sauvegarde des résultats")
            raw_scenarios = result.get("scenarios", [])

            prepared_scenarios: List[dict] = []
            for idx, entry in enumerate(raw_scenarios, start=1):
                if not isinstance(entry, dict):
                    continue
                cloned = dict(entry)
                cloned.setdefault("scenario_index", idx)
                if "scenario" not in cloned and any(key in cloned for key in ("parties", "titre", "texte_narration")):
                    payload = {k: v for k, v in cloned.items() if k not in {"structure", "timeline"}}
                    cloned["scenario"] = payload
                prepared_scenarios.append(cloned)

            session_store.update_session(req.session_id, {"scenarios": prepared_scenarios})
            finish_step(3, "Scénarios prêts pour la relecture")
        except HTTPException as http_err:
            mark(current_step, "error", str(http_err.detail) if hasattr(http_err, "detail") else str(http_err))
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Scenario generation failed for session %s", req.session_id)
            mark(current_step, "error", str(exc))
            raise

        log_progress(
            "SCENARIO_GENERATE_DONE",
            session=req.session_id,
            project=project_name,
            scenarios=scenario_count,
        )
        details = {
            "skill_metadata": result.get("skill_metadata", {}),
            "status": result.get("status"),
        }
        return ScenarioGenerationResponse(
            status=result.get("status", "unknown"),
            scenario_count=scenario_count,
            output_dir=result.get("skill_metadata", {}).get("output_dir", req.output_dir),
            details=details,
        )

    @app.get("/sessions/{session_id}/scenarios", tags=["sessions"])
    async def get_generated_scenarios(session_id: str) -> dict:
        scenarios = session_store.get_scenarios(session_id)
        return {"scenarios": scenarios}

    @app.get("/sessions/{session_id}/scenario-selection", response_model=ScenarioSelectionResponse, tags=["sessions"])
    async def get_selected_scenario(session_id: str) -> ScenarioSelectionResponse:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return ScenarioSelectionResponse(scenario=session.get("selected_scenario"))

    @app.post("/sessions/{session_id}/scenario-selection", tags=["sessions"])
    async def choose_scenario(session_id: str, payload: ScenarioSelectionPayload):
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if not payload.scenario:
            raise HTTPException(status_code=400, detail="Scenario payload required")
        session_store.set_selected_scenario(session_id, payload.scenario)
        scenario_title = payload.scenario.get("titre") or payload.scenario.get("title")
        log_progress(
            "SCENARIO_SELECTED",
            session=session_id,
            project=session["project_name"],
            title=scenario_title,
        )
        return {"status": "ok"}

    @app.get("/sessions/{session_id}/scenario-audio", tags=["sessions"])
    async def get_scenario_audio(session_id: str) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        metadata = session_store.get_scenario_audio(session_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Aucun audio généré pour ce scénario")
        return metadata

    @app.post("/sessions/{session_id}/scenario-audio", tags=["sessions"])
    async def synthesize_scenario_audio(session_id: str, payload: ScenarioAudioRequest) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        scenario = session.get("selected_scenario")
        if not scenario:
            raise HTTPException(status_code=400, detail="Aucun scénario sélectionné")
        text = (payload.text or scenario_to_text(scenario)).strip()
        if not text:
            raise HTTPException(status_code=400, detail="Impossible de générer l'audio : texte vide")
        log_progress(
            "SCENARIO_AUDIO_START",
            session=session_id,
            project=session["project_name"],
            language=payload.language or "French",
        )
        def synthesize() -> dict:
            return text_to_speech_with_instructions(
                text=text,
                project_name=session["project_name"],
                language=payload.language or "French",
            )

        try:
            result = synthesize()
        except ValueError as exc:
            message = str(exc)
            lowered = message.lower()
            if any(token in lowered for token in ["aucune voix", "no voice", "voice instructions"]):
                logger.info("Voice instructions missing for %s – composing default", session["project_name"])
                try:
                    ensure_voice_instructions(session["project_name"], text, payload.language or "French")
                except Exception as inner_exc:  # pragma: no cover - fallback message
                    raise HTTPException(status_code=400, detail=str(inner_exc)) from inner_exc
                try:
                    result = synthesize()
                except Exception as retry_exc:
                    raise HTTPException(status_code=400, detail=str(retry_exc)) from retry_exc
            else:
                raise HTTPException(status_code=400, detail=message) from exc
        except Exception as exc:  # pragma: no cover - propagate to client
            logger.exception("Scenario audio synthesis failed for session %s", session_id)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        metadata = {
            **result,
            "generated_at": datetime.utcnow().isoformat(),
            "text_length": len(text),
            "language": payload.language or "French",
        }
        session_store.save_scenario_audio(session_id, metadata)
        log_progress(
            "SCENARIO_AUDIO_DONE",
            session=session_id,
            project=session["project_name"],
            path=metadata.get("path"),
            duration=metadata.get("num_samples"),
        )
        return metadata

    @app.get("/sessions/{session_id}/scenario-audio/file", tags=["sessions"])
    async def stream_scenario_audio(session_id: str):
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        metadata = session_store.get_scenario_audio(session_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Aucun audio généré pour ce scénario")
        path_value = metadata.get("path")
        if not path_value:
            raise HTTPException(status_code=404, detail="Chemin audio manquant")
        audio_path = Path(path_value)
        if not audio_path.is_absolute():
            audio_path = (Path.cwd() / audio_path).resolve()
        if not audio_path.exists():
            raise HTTPException(status_code=404, detail="Fichier audio introuvable")
        return FileResponse(audio_path)

    @app.post("/projects/{project_name}/audio", tags=["projects"])
    async def upload_audio(project_name: str, file: UploadFile = File(...)) -> dict:
        automation_runner.ensure_project_exists(project_name)
        contents = await file.read()
        try:
            meta = validate_audio_file(file.filename, contents, settings.max_audio_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        audio_dir = settings.projects_dir / project_name / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        target = audio_dir / file.filename
        with open(target, "wb") as f:
            f.write(contents)

        session_store.append_project_file(project_name, str(target))
        log_progress(
            "AUDIO_UPLOADED",
            project=project_name,
            file=file.filename,
            size=len(contents),
        )

        transcription_status = {"status": "skipped"}
        try:
            await transcribe_and_store(project_name, target, meta)
            transcription_status = {"status": "ok"}
        except Exception as exc:
            transcription_status = {"status": "error", "message": str(exc)}

        return {
            "status": "uploaded",
            "path": str(target),
            "metadata": meta,
            "transcription": transcription_status,
        }

    @app.get("/projects/{project_name}/audio", tags=["projects"])
    async def list_project_audio_endpoint(project_name: str) -> dict:
        automation_runner.ensure_project_exists(project_name)
        files = list_project_audio_files(project_name)
        return {"files": files}

    @app.get("/projects/{project_name}/final-audio", tags=["projects"])
    async def stream_project_audio(project_name: str):
        profile = load_project_profile(project_name)
        metadata = profile.get("final_audio")
        if not metadata or not metadata.get("path"):
            raise HTTPException(status_code=404, detail="Aucun audio final pour ce projet")
        audio_path = Path(metadata["path"])
        if not audio_path.is_absolute():
            audio_path = (Path.cwd() / audio_path).resolve()
        if not audio_path.exists():
            raise HTTPException(status_code=404, detail="Fichier audio introuvable")
        return FileResponse(audio_path)

    @app.get("/sessions/{session_id}/audio-selection", tags=["sessions"])
    async def get_audio_selection(session_id: str) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        selection = load_audio_selection(session["project_name"])
        return selection

    @app.get("/sessions/{session_id}/scenario-progress", tags=["sessions"])
    async def get_scenario_progress(session_id: str) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        steps = session_store.get_scenario_progress(session_id)
        return {"steps": steps}

    @app.post("/sessions/{session_id}/audio-selection", tags=["sessions"])
    async def update_audio_selection(session_id: str, payload: AudioSelectionPayload) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["project_name"] != payload.project_name:
            raise HTTPException(status_code=400, detail="Project mismatch for session")
        available_voices = set(list_project_audio_files(payload.project_name))
        voices = [track for track in payload.voices if track in available_voices][:3]
        backgrounds = payload.backgrounds[:2]
        saved = save_audio_selection(payload.project_name, {"voices": voices, "backgrounds": backgrounds})
        log_progress(
            "AUDIO_SELECTION_UPDATED",
            session=session_id,
            project=payload.project_name,
            voices=len(voices),
            backgrounds=len(backgrounds),
        )
        return saved

    @app.get("/sessions/{session_id}/agent-outputs", tags=["sessions"])
    async def get_agent_outputs(session_id: str) -> dict:
        """Return the intermediate outputs produced by each agent during scenario generation."""
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        outputs = session_store.get_agent_outputs(session_id)
        if not outputs:
            raise HTTPException(status_code=404, detail="Aucune sortie d'agent disponible pour cette session")
        return outputs

    @app.get("/logs/recent", tags=["system"])
    async def get_recent_logs(
        lines: int = Query(default=100, ge=1, le=1000, description="Nombre de lignes à retourner"),
    ) -> dict:
        """Return the N most recent lines from the application log file."""
        log_file = Path(os.getenv("LOG_FILE", "./logs/memoire_territoires.log"))
        if not log_file.exists():
            return {"lines": [], "file": str(log_file), "message": "Log file not found"}
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
            recent = all_lines[-lines:]
            return {
                "lines": [line.rstrip("\n") for line in recent],
                "total_lines": len(all_lines),
                "returned": len(recent),
                "file": str(log_file),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Erreur de lecture des logs: {exc}") from exc

    @app.get("/background-sounds", tags=["media"])
    async def list_background_sounds(
        keyword: Optional[str] = Query(default=None, description="Filtrer par mot-clé"),
        limit: int = Query(default=50, le=200, gt=0),
    ) -> dict:
        try:
            listing = find_background_sounds(keyword=keyword, limit=limit)
        except FileNotFoundError:
            listing = {"files": [], "status": "ok"}
        files = []
        for rel in listing.get("files", []):
            files.append(
                {
                    "path": rel,
                    "name": Path(rel).name,
                    "preview": f"/background-sounds/preview?path={quote(rel)}",
                }
            )
        listing["files"] = files
        return listing

    @app.get("/background-sounds/preview", tags=["media"])
    async def preview_background_sound(path: str = Query(..., description="Chemin relatif du son")):
        file_path = resolve_background_path(path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Fichier introuvable")
        return FileResponse(file_path)

    @app.post("/background-sounds/upload", tags=["media"])
    async def upload_background_sound(
        title: str = Form(..., description="Nom de la nouvelle ambiance"),
        file: UploadFile = File(...),
    ) -> dict:
        contents = await file.read()
        try:
            validate_audio_file(file.filename, contents, settings.max_audio_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        folder_name = slugify(title)
        target_dir = background_root / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_name = file.filename or f"{folder_name}.wav"
        target_path = target_dir / safe_name
        with open(target_path, "wb") as f:
            f.write(contents)

        rel_path = Path("data/audio/background_sounds") / target_path.relative_to(background_root)
        log_progress(
            "BACKGROUND_SOUND_UPLOADED",
            title=title,
            file=safe_name,
            size=len(contents),
        )
        return {
            "status": "uploaded",
            "path": str(rel_path),
            "preview": f"/background-sounds/preview?path={quote(str(rel_path))}",
        }

    @app.websocket("/ws/chat")
    async def websocket_endpoint(websocket: WebSocket):
        session_id = websocket.query_params.get("session_id")
        if not session_id:
            await websocket.close(code=4401)
            return
        session = session_store.load_session(session_id)
        if not session:
            await websocket.close(code=4404)
            return
        await websocket.accept()
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "message": "Payload invalide"})
                    continue
                text = payload.get("text")
                if not text:
                    await websocket.send_json({"type": "error", "message": "Message vide"})
                    continue
                await chat_agent.handle_message(session_id, text, session_store, websocket)
        except WebSocketDisconnect:
            logger.info("websocket disconnected")

    frontend_dir = settings.frontend_dist
    if frontend_dir.exists():
        app.mount("/web", StaticFiles(directory=frontend_dir, html=True), name="frontend")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            file_path = frontend_dir / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            index_file = frontend_dir / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            raise HTTPException(status_code=404, detail="Asset not found")

    return app
