"""FastAPI application exposing the Mémoire des Territoires toolchain."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Query, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from memoiredesterritoires.scenario_maker import ScenarioMakerSkill
from memoiredesterritoires.background_sound_finder.background_sound_finder import find_background_sounds
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

        if payload.description:
            automation_runner.update_project_notes(payload.name, payload.description)

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
                    projects.append({"name": child.name, "scenario_target": meta.get("scenario_target", 3)})
        return {"projects": projects}

    @app.post("/sessions", tags=["sessions"])
    async def create_session(payload: SessionCreateRequest) -> dict:
        automation_runner.ensure_project_exists(payload.project_name)
        settings_meta = load_project_settings(payload.project_name)
        target = payload.scenario_target or settings_meta.get("scenario_target", 3)
        session = session_store.create_session(payload.project_name, payload.initial_step, scenario_target=target)
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

        if payload.step_id == "scenario_review":
            files = payload.payload.get("files") if payload.payload else None
            if not files:
                raise HTTPException(status_code=400, detail="Sélectionnez au moins une piste audio avant de continuer")
        if payload.step_id == "scenario_edit" and not session.get("selected_scenario"):
            raise HTTPException(status_code=400, detail="Sélectionnez d'abord un scénario")
        if payload.step_id == "final_validation" and not session.get("selected_scenario"):
            raise HTTPException(status_code=400, detail="Aucun scénario sélectionné")

        session_store.update_session(session_id, {
            "current_step": payload.step_id,
            "steps": {payload.step_id: payload.payload},
        })
        results = automation_runner.run(payload.step_id, session["project_name"], payload.payload)
        return {"session_id": session_id, "step": payload.step_id, "automations": results}

    @app.post("/scenarios/generate", response_model=ScenarioGenerationResponse, tags=["scenarios"])
    async def generate_scenarios(req: ScenarioGenerationRequest):
        session = session_store.load_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        params = {
            "prompt": req.prompt,
            "mode": req.mode,
            "output_dir": req.output_dir,
            "scenario_target": req.scenario_target or session.get("scenario_target", 3),
        }
        logger.info(
            "Generating scenarios (session=%s project=%s target=%s)",
            req.session_id,
            session["project_name"],
            params["scenario_target"],
        )
        result = scenario_skill.run(params)
        logger.info("Scenario generation completed for session %s", req.session_id)
        details = {
            "skill_metadata": result.get("skill_metadata", {}),
            "status": result.get("status"),
        }
        session_store.update_session(req.session_id, {"scenarios": result.get("scenarios", [])})
        return ScenarioGenerationResponse(
            status=result.get("status", "unknown"),
            scenario_count=result.get("skill_metadata", {}).get("scenario_count", 0),
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
        return {"status": "ok"}

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

        return {"status": "uploaded", "path": str(target), "metadata": meta}

    @app.get("/projects/{project_name}/audio", tags=["projects"])
    async def list_project_audio_endpoint(project_name: str) -> dict:
        automation_runner.ensure_project_exists(project_name)
        files = list_project_audio_files(project_name)
        return {"files": files}

    @app.get("/sessions/{session_id}/audio-selection", tags=["sessions"])
    async def get_audio_selection(session_id: str) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        selection = load_audio_selection(session["project_name"])
        return selection

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
        return saved

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
