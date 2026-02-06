"""FastAPI application exposing the Mémoire des Territoires toolchain."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from memoiredesterritoires.scenario_maker import ScenarioMakerSkill

from .config import AppSettings, get_settings
from .session_store import SessionStore
from .step_config import StepConfigRegistry
from .automation import AutomationRunner
from .audio_validation import validate_audio_file

logger = logging.getLogger(__name__)


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., description="Human readable project name")
    description: Optional[str] = Field(None, description="Optional blurb saved into project notes")


class SessionCreateRequest(BaseModel):
    project_name: str
    initial_step: str = "project_selection"


class StepTransitionRequest(BaseModel):
    step_id: str
    payload: dict = Field(default_factory=dict)


class ScenarioGenerationRequest(BaseModel):
    session_id: str
    prompt: str
    mode: str = "simple"
    output_dir: str = "./output"


class ScenarioGenerationResponse(BaseModel):
    status: str
    scenario_count: int
    output_dir: str
    details: dict


def create_app(settings: Optional[AppSettings] = None) -> FastAPI:
    settings = settings or get_settings()
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

        if payload.description:
            automation_runner.update_project_notes(payload.name, payload.description)

        return {
            "project": payload.name,
            "path": str(project_dir),
        }

    @app.get("/projects", tags=["projects"])
    async def list_projects() -> dict:
        projects: List[str] = []
        if settings.projects_dir.exists():
            for child in sorted(settings.projects_dir.iterdir()):
                if child.is_dir():
                    projects.append(child.name)
        return {"projects": projects}

    @app.post("/sessions", tags=["sessions"])
    async def create_session(payload: SessionCreateRequest) -> dict:
        automation_runner.ensure_project_exists(payload.project_name)
        session = session_store.create_session(payload.project_name, payload.initial_step)
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
        }
        result = scenario_skill.run(params)
        details = {
            "skill_metadata": result.get("skill_metadata", {}),
            "status": result.get("status"),
        }
        return ScenarioGenerationResponse(
            status=result.get("status", "unknown"),
            scenario_count=result.get("skill_metadata", {}).get("scenario_count", 0),
            output_dir=result.get("skill_metadata", {}).get("output_dir", req.output_dir),
            details=details,
        )

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

    @app.websocket("/ws/chat")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"echo:{data}")
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
