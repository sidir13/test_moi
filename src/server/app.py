"""FastAPI application exposing the Mémoire des Territoires toolchain."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import shutil
import tempfile
from functools import lru_cache
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Query, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

from memoiredesterritoires.scenario_maker import ScenarioMakerSkill
from memoiredesterritoires.scenario_ranking.rank_scenarios import rank_scenarios_against_config
from memoiredesterritoires.background_sound_finder.background_sound_finder import find_background_sounds
from memoiredesterritoires.text_to_speech_with_instructions.text_to_speech_with_instructions import (
    text_to_speech_with_instructions,
)
from memoiredesterritoires.elevenlabs_tts.elevenlabs_tts import eleven_labs_tts
from memoiredesterritoires.transcription.transcription_parallelized import transcribe_audio
from memoiredesterritoires.analysis_storage.analysis_storage import save_analysis_result, fetch_analysis_results
from memoiredesterritoires.Slideshow.slides import slideshow
from memoiredesterritoires.project_config import (
    get_project_config_path,
    load_project_config,
    save_project_config,
)
from project_store import (
    load_project_settings,
    save_project_settings,
    load_audio_selection,
    save_audio_selection,
    list_project_audio_files,
)
from pydub import AudioSegment

from .config import AppSettings, get_settings
from .session_store import SessionStore
from .step_config import StepConfigRegistry
from .automation import AutomationRunner
from .chat_agent import ChatAgent
from .audio_validation import validate_audio_file
from utils.claude_client import ClaudeClient

from config.model_registry import get_available_models, resolve_model_id

logger = logging.getLogger(__name__)
SCENARIO_DEFAULT_CONFIG_PATH = Path(os.getenv("SCENARIO_DEFAULT_CONFIG", "config/default_config.json")).expanduser()
BACKGROUND_ATTENUATION_DB = 20 * math.log10(0.15)  # ≈ -16.48 dB
BACKGROUND_PLAN_MODEL = os.getenv("BACKGROUND_PLAN_MODEL", "anthropic/claude-sonnet-4-5")
VOICE_TRANSLATION_MODEL = os.getenv("VOICE_TRANSLATION_MODEL", "anthropic/claude-3-haiku-20240307")
MIN_BACKGROUND_SEGMENT = 5.0
MAX_BACKGROUND_SEGMENT = 10.0
BACKGROUND_SEGMENT_GAP = 0.5
_background_plan_client: Optional[ClaudeClient] = None
_voice_translation_client: Optional[ClaudeClient] = None
FRENCH_HINT_KEYWORDS = {
    "voix",
    "femme",
    "homme",
    "ans",
    "ton",
    "posé",
    "posée",
    "pédagogue",
    "doux",
    "douce",
    "grave",
    "rapide",
    "lent",
    "accent",
}


class TTSJob(TypedDict):
    job_id: str
    session_id: str
    project_name: str
    text: str
    language: str
    provider: str
    voice_id: Optional[str]
    requested_at: str


@lru_cache(maxsize=1)
def _load_generation_preference_defaults() -> Dict[str, Any]:
    if not SCENARIO_DEFAULT_CONFIG_PATH.exists():
        logger.warning("Default scenario config not found at %s", SCENARIO_DEFAULT_CONFIG_PATH)
        return {}
    try:
        with open(SCENARIO_DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON in %s: %s", SCENARIO_DEFAULT_CONFIG_PATH, exc)
        return {}
    return payload.get("scenario_config", {}).get("generation_parameters", {})


def _get_preference_options() -> Dict[str, Any]:
    defaults = _load_generation_preference_defaults()
    tone = defaults.get("ton", {})
    audience = defaults.get("public_cible", {})
    duration = defaults.get("duree", {})
    duration_range = duration.get("range") or [30, 600]
    if not isinstance(duration_range, list) or len(duration_range) != 2:
        duration_range = [30, 600]
    try:
        duration_min = int(duration_range[0])
        duration_max = int(duration_range[1])
    except (TypeError, ValueError):
        duration_min, duration_max = 30, 600
    return {
        "tone_options": tone.get("options", []),
        "audience_options": audience.get("options", []),
        "duration": {
            "min": duration_min,
            "max": duration_max,
            "default": int(duration.get("value") or duration.get("default") or 120),
            "step": int(duration.get("step") or 10),
        },
    }


def log_progress(event: str, **fields: Any) -> None:
    if not fields:
        logger.info(event)
        return
    details = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    logger.info("%s | %s", event, details)


def _get_background_plan_client() -> Optional[ClaudeClient]:
    global _background_plan_client
    if _background_plan_client is not None:
        return _background_plan_client
    try:
        _background_plan_client = ClaudeClient()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Unable to initialize Claude client for background planning: %s", exc)
        return None
    return _background_plan_client


def _get_voice_translation_client() -> Optional[ClaudeClient]:
    global _voice_translation_client
    if _voice_translation_client is not None:
        return _voice_translation_client
    try:
        _voice_translation_client = ClaudeClient()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Unable to initialize Claude client for voice translation: %s", exc)
        return None
    return _voice_translation_client


def _extract_json_array(payload: str) -> List[Dict[str, Any]]:
    try:
        parsed = json.loads(payload)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[[\s\S]+\]", payload)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return []
    return []


def _fallback_background_plan(duration_seconds: float, background_count: int) -> List[Dict[str, float]]:
    if background_count <= 0 or duration_seconds <= 0:
        return []
    slot_duration = min(MAX_BACKGROUND_SEGMENT, max(MIN_BACKGROUND_SEGMENT, duration_seconds * 0.1))
    spacing = duration_seconds / (background_count + 1)
    plan: List[Dict[str, float]] = []
    for idx in range(background_count):
        start = spacing * (idx + 1) - slot_duration / 2
        start = max(0.0, min(start, max(0.0, duration_seconds - slot_duration)))
        plan.append(
            {
                "background_index": idx,
                "start_seconds": start,
                "duration_seconds": slot_duration,
                "note": "Fallback placement",
            }
        )
    return plan


def _sanitize_background_plan(
    raw_plan: List[Dict[str, Any]],
    duration_seconds: float,
    background_count: int,
) -> List[Dict[str, float]]:
    if duration_seconds <= 0 or background_count <= 0:
        return []
    sanitized: List[Dict[str, float]] = []
    used_indexes: set[int] = set()
    last_end = 0.0
    for entry in sorted(raw_plan, key=lambda item: float(item.get("start_seconds", 0.0))):
        try:
            idx = int(entry.get("background_index"))
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= background_count or idx in used_indexes:
            continue
        try:
            start = float(entry.get("start_seconds", 0.0))
        except (TypeError, ValueError):
            start = 0.0
        try:
            duration = float(entry.get("duration_seconds", MIN_BACKGROUND_SEGMENT))
        except (TypeError, ValueError):
            duration = MIN_BACKGROUND_SEGMENT
        duration = max(MIN_BACKGROUND_SEGMENT, min(MAX_BACKGROUND_SEGMENT, duration))
        if start < last_end + BACKGROUND_SEGMENT_GAP:
            start = last_end + BACKGROUND_SEGMENT_GAP
        if start + duration > duration_seconds:
            start = max(0.0, duration_seconds - duration)
        if start < last_end + BACKGROUND_SEGMENT_GAP:
            continue
        if start + duration > duration_seconds or duration < MIN_BACKGROUND_SEGMENT:
            continue
        note = entry.get("note") or entry.get("context") or entry.get("moment")
        sanitized.append(
            {
                "background_index": idx,
                "start_seconds": round(start, 3),
                "duration_seconds": round(duration, 3),
                "note": note.strip() if isinstance(note, str) else None,
            }
        )
        used_indexes.add(idx)
        last_end = start + duration
        if len(sanitized) >= background_count:
            break
    return sanitized


def plan_background_segments(
    scenario_text: Optional[str],
    duration_seconds: float,
    background_files: List[Path],
) -> List[Dict[str, float]]:
    background_count = len(background_files)
    if background_count == 0 or duration_seconds <= MIN_BACKGROUND_SEGMENT:
        return []

    scenario_excerpt = ""
    if scenario_text:
        scenario_excerpt = re.sub(r"\s+", " ", scenario_text).strip()
        max_chars = 1500
        if len(scenario_excerpt) > max_chars:
            scenario_excerpt = scenario_excerpt[:max_chars] + "…"

    raw_plan: List[Dict[str, Any]] = []
    client = _get_background_plan_client() if scenario_excerpt else None
    if client:
        available_lines = [
            f"{idx}: {bg.name}"
            for idx, bg in enumerate(background_files)
        ]
        available_listing = "\n".join(available_lines)
        user_prompt = (
            "You plan short ambience cues under a narration. "
            "Constraints:\n"
            "- Each ambience plays exactly once.\n"
            "- Each cue must last between 5 and 10 seconds.\n"
            "- Cues must never overlap; keep at least 0.5s gap.\n"
            "- Never exceed the narration length.\n\n"
            f"Narration duration: {duration_seconds:.1f} seconds.\n"
            "Available ambiences (index: file):\n"
            f"{available_listing}\n\n"
            "Script excerpt:\n"
            f"{scenario_excerpt}\n\n"
            "Return ONLY a JSON array like:\n"
            '[{"background_index": 0, "start_seconds": 12.5, "duration_seconds": 7.0, "note": "support intro"}]\n'
            "Use narrative cues to place the backgrounds."
        )
        try:
            response = client.create_message(
                model=BACKGROUND_PLAN_MODEL,
                system="You are an audio post-production planner who schedules short ambience cues.",
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.2,
                max_tokens=600,
            )
            raw_text = ""
            if response and getattr(response, "content", None):
                raw_text = response.content[0].text  # type: ignore[attr-defined]
            raw_plan = _extract_json_array(raw_text)
        except Exception as exc:  # pragma: no cover - network
            logger.warning("Background planning via LLM failed: %s", exc)

    if not raw_plan:
        raw_plan = _fallback_background_plan(duration_seconds, background_count)

    plan = _sanitize_background_plan(raw_plan, duration_seconds, background_count)
    if not plan:
        plan = _sanitize_background_plan(
            _fallback_background_plan(duration_seconds, background_count),
            duration_seconds,
            background_count,
        )
    return plan


def apply_background_selection(
    voice_path: Path,
    project_name: str,
    scenario_text: Optional[str] = None,
) -> tuple[Path, int, Optional[Path], int, List[Dict[str, Any]]]:
    """
    Mix the user-selected background sounds under the generated narration.

    Returns:
        (final_voice_path, layers_applied, dry_voice_path, requested_layers, plan_metadata)
    """
    try:
        selection = load_audio_selection(project_name)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Unable to load audio selection for %s: %s", project_name, exc)
        selection = {}

    raw_backgrounds = selection.get("backgrounds") or []
    normalized_paths: List[Path] = []
    for entry in raw_backgrounds:
        if not entry:
            continue
        resolved = Path(entry)
        if not resolved.is_absolute():
            resolved = (Path.cwd() / resolved).resolve()
        normalized_paths.append(resolved)

    requested_layers = len(normalized_paths)
    if requested_layers == 0:
        return voice_path, 0, None, requested_layers, []
    if AudioSegment is None:
        logger.warning("pydub is not available; skipping background mix for %s", project_name)
        return voice_path, 0, None, requested_layers, []

    resolved_voice = Path(voice_path)
    if not resolved_voice.is_absolute():
        resolved_voice = (Path.cwd() / resolved_voice).resolve()
    if not resolved_voice.exists():
        logger.warning("Voice file missing for background mix: %s", resolved_voice)
        return voice_path, 0, None, requested_layers, []

    try:
        voice_segment = AudioSegment.from_file(resolved_voice)
    except Exception as exc:
        logger.warning("Unable to load narration audio (%s): %s", resolved_voice, exc)
        return voice_path, 0, None, requested_layers, []

    duration_seconds = len(voice_segment) / 1000.0
    plan = plan_background_segments(scenario_text, duration_seconds, normalized_paths)
    if not plan:
        logger.info("No background plan generated for %s; leaving narration dry", project_name)
        return voice_path, 0, None, requested_layers, []

    mixed_segment = voice_segment
    used_indexes: set[int] = set()
    plan_metadata: List[Dict[str, Any]] = []
    background_cache: Dict[int, AudioSegment] = {}

    total_backgrounds = len(normalized_paths)
    for slot in plan:
        idx = int(slot["background_index"])
        if idx < 0 or idx >= total_backgrounds:
            continue
        bg_path = normalized_paths[idx]
        if not bg_path.exists():
            logger.warning("Background sound not found: %s", bg_path)
            continue
        background_segment = background_cache.get(idx)
        try:
            if background_segment is None:
                background_segment = AudioSegment.from_file(bg_path)
                background_cache[idx] = background_segment
        except Exception as exc:
            logger.warning("Failed to load background %s: %s", bg_path, exc)
            continue
        start_ms = max(0, int(slot["start_seconds"] * 1000))
        duration_ms = max(1, int(slot["duration_seconds"] * 1000))
        if start_ms >= len(mixed_segment):
            continue
        snippet = background_segment
        if len(snippet) < duration_ms:
            repeats = max(1, math.ceil(duration_ms / max(len(snippet), 1)))
            snippet = snippet * repeats
        snippet = snippet[:duration_ms]
        snippet = snippet + BACKGROUND_ATTENUATION_DB
        available = len(mixed_segment) - start_ms
        if available <= 0:
            continue
        snippet = snippet[:available]
        mixed_segment = mixed_segment.overlay(snippet, position=start_ms)
        used_indexes.add(idx)
        plan_metadata.append(
            {
                "background": bg_path.name,
                "start_seconds": round(start_ms / 1000, 2),
                "duration_seconds": round(len(snippet) / 1000, 2),
                "note": slot.get("note"),
            }
        )

    if not used_indexes:
        return voice_path, 0, None, requested_layers, []

    output_format = resolved_voice.suffix.replace(".", "") or "wav"
    temp_mix = resolved_voice.with_name(f"{resolved_voice.stem}_mix{resolved_voice.suffix}")
    mixed_segment.export(
        str(temp_mix),
        format=output_format,
        parameters=["-ar", str(voice_segment.frame_rate)],
    )
    dry_path = resolved_voice.with_name(f"{resolved_voice.stem}_dry{resolved_voice.suffix}")
    if dry_path.exists():
        dry_path.unlink()
    resolved_voice.replace(dry_path)
    temp_mix.replace(resolved_voice)

    # Return the path in the same shape as input (relative or absolute)
    final_path = Path(voice_path)
    if not final_path.is_absolute():
        try:
            final_path = resolved_voice.relative_to(Path.cwd())
        except ValueError:
            final_path = resolved_voice
    else:
        final_path = resolved_voice

    dry_relative: Optional[Path] = dry_path
    if dry_path:
        if not voice_path.is_absolute():
            try:
                dry_relative = dry_path.relative_to(Path.cwd())
            except ValueError:
                dry_relative = dry_path

    return final_path, len(used_indexes), dry_relative, requested_layers, plan_metadata


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
    model_id: Optional[str] = Field(default=None, description="Model key (opus, sonnet, gemini) or full OpenRouter ID")


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
    tts_voice_id: Optional[str] = Field(default=None, description="Selected ElevenLabs voice identifier")


class ScenarioAudioRequest(BaseModel):
    text: Optional[str] = None
    language: str = Field(default="French")


class ImageOrderPayload(BaseModel):
    order: List[str]


def create_app(settings: Optional[AppSettings] = None) -> FastAPI:
    settings = settings or get_settings()
    os.environ.setdefault("PROJECTS_DIR", str(settings.projects_dir))
    app = FastAPI(title="Mémoire des Territoires API", version="0.1.0")
    app.state.tts_queue = None
    app.state.tts_worker = None
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

    # ── Model selection endpoint ──────────────────────────────────
    @app.get("/models", tags=["models"])
    async def list_models():
        """Return available LLM models for scenario generation."""
        return {"models": get_available_models()}

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
        summary = payload.get("resume") or payload.get("texte") or payload.get("texte_narration")
        parties = payload.get("parties")
        if isinstance(parties, list) and parties:
            for part in parties:
                if not isinstance(part, dict):
                    continue
                part_lines = []
                if isinstance(part.get("texte_narration"), str):
                    part_lines.append(part["texte_narration"].strip())
                elif isinstance(part.get("texte"), str):
                    part_lines.append(part["texte"].strip())
                if part_lines:
                    chunks.append("\n".join(part_lines))
        elif isinstance(summary, str):
            chunks.append(summary.strip())

        return "\n\n".join([chunk for chunk in chunks if chunk]).strip()

    def compute_scenario_ranking(
        config: Optional[Dict[str, Any]],
        scenarios: List[Dict[str, Any]],
        project_name: str,
    ) -> List[int]:
        if not config or not scenarios:
            return []
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                config_path = tmpdir_path / "config.json"
                scenario_dir = tmpdir_path / "scenarios"
                scenario_dir.mkdir(parents=True, exist_ok=True)
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                name_to_index: Dict[str, int] = {}
                for idx, entry in enumerate(scenarios, start=1):
                    payload = entry.get("scenario")
                    if not isinstance(payload, dict):
                        continue
                    file_name = f"scenario_{idx}.json"
                    with open(scenario_dir / file_name, "w", encoding="utf-8") as f:
                        json.dump(payload, f, ensure_ascii=False, indent=2)
                    name_to_index[file_name] = idx
                if not name_to_index:
                    return []
                ranking_result = rank_scenarios_against_config(
                    config_path=str(config_path),
                    scenarios_dir=str(scenario_dir),
                    project_name=project_name,
                )
            ordered_indexes: List[int] = []
            for name in ranking_result.get("ranking", []):
                normalized = Path(name).name
                idx = name_to_index.get(normalized)
                if idx is not None and idx not in ordered_indexes:
                    ordered_indexes.append(idx)
            return ordered_indexes
        except Exception as exc:
            logger.warning("Scenario ranking failed for %s: %s", project_name, exc)
            return []

    def _normalize_requirement_value(value: Optional[str]) -> str:
        if not value:
            return ""
        return value.replace("_", " ").replace("-", " ").strip()

    def build_project_constraints(profile: Dict[str, Any]) -> Dict[str, Any]:
        scenario_config = profile.get("scenario_config") or {}
        gen_params = scenario_config.get("generation_parameters") or {}

        def _from_config(key: str) -> Optional[str]:
            if not isinstance(gen_params, dict):
                return None
            entry = gen_params.get(key)
            if isinstance(entry, dict):
                return entry.get("value")
            return None

        audience = profile.get("audience") or _from_config("public_cible")
        tone = profile.get("tone") or _from_config("ton")
        duration = profile.get("target_duration") or _from_config("duree")
        try:
            duration_value = int(duration) if duration is not None else None
        except (TypeError, ValueError):
            duration_value = None
        voice = profile.get("voice_instructions")
        norm_audience = _normalize_requirement_value(audience).lower()
        norm_tone = _normalize_requirement_value(tone).lower()
        audience_tokens: List[str] = []
        if norm_audience:
            audience_tokens.append(norm_audience)
            if "enfant" in norm_audience:
                audience_tokens.extend(
                    ["enfant", "enfants", "mon enfant", "mon fils", "ma fille"]
                )
        constraints = {
            "audience": audience,
            "audience_norm": norm_audience,
            "audience_tokens": audience_tokens,
            "tone": tone,
            "tone_norm": norm_tone,
            "duration": duration_value,
            "voice": voice,
            "require_intro_context": True,
        }
        constraints["has_requirements"] = any(
            constraints.get(key) for key in ("audience", "tone", "duration", "voice")
        )
        return constraints

    def build_config_overrides_from_constraints(constraints: Dict[str, Any]) -> Dict[str, Any]:
        if not constraints.get("has_requirements"):
            return {}
        overrides: Dict[str, Any] = {}
        scenario_config = overrides.setdefault("scenario_config", {})
        gen_params = scenario_config.setdefault("generation_parameters", {})
        if constraints.get("audience"):
            gen_params["public_cible"] = {
                "value": constraints["audience"],
                "user_specified": True,
                "source": "project_profile",
            }
        if constraints.get("tone"):
            gen_params["ton"] = {
                "value": constraints["tone"],
                "user_specified": True,
                "source": "project_profile",
            }
        if constraints.get("duration"):
            gen_params["duree"] = {
                "value": constraints["duration"],
                "unit": "secondes",
                "user_specified": True,
                "source": "project_profile",
            }
        metadata = scenario_config.setdefault("metadata", {})
        metadata.setdefault("project_constraints", {}).update(
            {
                "audience": constraints.get("audience"),
                "tone": constraints.get("tone"),
                "duration_seconds": constraints.get("duration"),
                "voice_instructions": constraints.get("voice"),
            }
        )
        metadata.setdefault("hard_requirements", {}).update(
            {
                "must_reference_audience_in_intro": constraints.get("require_intro_context"),
                "enforce_project_tone": bool(constraints.get("tone")),
                "enforce_project_duration": bool(constraints.get("duration")),
            }
        )
        return overrides

    def build_constraint_prompt_block(constraints: Dict[str, Any]) -> str:
        if not constraints.get("has_requirements"):
            return ""
        lines = [
            "=== CONTRAINTES NON NÉGOCIABLES ===",
        ]
        if constraints.get("audience"):
            lines.append(f"- Public cible : {constraints['audience']} (adapte le vocabulaire et rappelle-le dès l'ouverture).")
        if constraints.get("tone"):
            lines.append(f"- Ton narratif : {constraints['tone']} (ne change jamais de ton).")
        if constraints.get("duration"):
            minutes = constraints["duration"] // 60
            seconds = constraints["duration"] % 60
            lines.append(
                f"- Durée cible : ~{constraints['duration']} s ({minutes} min {seconds:02d}). Tolérance maximale ±15 %."
            )
        if constraints.get("voice"):
            lines.append(f"- Voix attendue : {constraints['voice']} (intègre cette intention dans la mise en scène).")
        lines.append("Commence la narration en présentant explicitement le public cible et le ton demandé.")
        lines.append("Tout écart à ces exigences doit être considéré comme une erreur.")
        return "\n".join(lines)

    def scenario_intro_snippet(entry: Dict[str, Any], max_chars: int = 400) -> str:
        payload = extract_scenario_payload(entry)
        snippets: List[str] = []
        parties = payload.get("parties")
        if isinstance(parties, list) and parties:
            for part in parties[:2]:
                text = part.get("texte_narration") if isinstance(part, dict) else None
                if text:
                    snippets.append(str(text).strip())
                if sum(len(s) for s in snippets) >= max_chars:
                    break
        elif isinstance(payload.get("texte_narration"), str):
            snippets.append(payload["texte_narration"].strip())
        intro = " ".join(snippets).strip()
        return intro[:max_chars]

    def intro_mentions_audience(text: str, constraints: Dict[str, Any]) -> bool:
        tokens = constraints.get("audience_tokens") or []
        if not tokens or not text:
            return True
        snippet = text.lower()
        return any(token in snippet for token in tokens)

    def assess_scenario_compliance(entry: Dict[str, Any], constraints: Dict[str, Any]) -> Dict[str, Any]:
        scenario_payload = extract_scenario_payload(entry)
        issues: List[str] = []
        tone_expected = constraints.get("tone_norm")
        tone_actual = _normalize_requirement_value(scenario_payload.get("ton", "")).lower()
        if tone_expected and tone_actual != tone_expected:
            issues.append(
                f"Ton attendu '{constraints.get('tone')}' mais obtenu '{scenario_payload.get('ton') or 'inconnu'}'."
            )

        expected_duration = constraints.get("duration")
        duration_actual = scenario_payload.get("duree_estimee")
        if duration_actual is None:
            timeline = entry.get("timeline")
            if isinstance(timeline, dict):
                duration_actual = timeline.get("duree_totale")
        if expected_duration and isinstance(expected_duration, int):
            try:
                duration_value = float(duration_actual)
            except (TypeError, ValueError):
                duration_value = None
            if duration_value is None:
                issues.append("Durée estimée indisponible.")
            else:
                tolerance = max(30.0, expected_duration * 0.15)
                if abs(duration_value - expected_duration) > tolerance:
                    issues.append(
                        f"Durée {int(duration_value)}s hors tolérance autour de {expected_duration}s."
                    )

        if constraints.get("require_intro_context"):
            intro = scenario_intro_snippet(entry)
            if not intro_mentions_audience(intro, constraints):
                issues.append("L'introduction ne rappelle pas le public cible fixé.")

        return {
            "is_compliant": not issues,
            "issues": issues,
        }

    def upsert_project_config_entry(project_name: str, updates: Dict[str, Any]) -> None:
        entry = load_project_config(
            project_name,
            projects_dir=settings.projects_dir,
            fallback_path=settings.config_json,
        )
        if "created_at" not in entry:
            entry["created_at"] = datetime.utcnow().isoformat()
        entry.setdefault("allowed_websites", ["wikipedia.org"])
        entry.setdefault("voice_instructions", "")
        entry.setdefault("voice_instructions_source", "")
        entry.setdefault("tts_provider", "qwen")
        for key, value in updates.items():
            if value is not None:
                entry[key] = value
        save_project_config(
            project_name,
            entry,
            projects_dir=settings.projects_dir,
        )

    def load_project_profile(project_name: str) -> Dict[str, Any]:
        return load_project_config(
            project_name,
            projects_dir=settings.projects_dir,
            fallback_path=settings.config_json,
        )

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

    def _extract_voice_hint(notes: Optional[str]) -> tuple[Optional[str], str]:
        if not notes:
            return None, ""
        voice_hint = None
        remaining: List[str] = []
        for raw_line in notes.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lower = line.lower()
            if voice_hint is None and ("voix" in lower or "voice" in lower or "narrateur" in lower or "narratrice" in lower):
                voice_hint = line
                continue
            remaining.append(line)
        return voice_hint, "\n".join(remaining).strip()

    def _maybe_translate_voice_hint(text: Optional[str]) -> Optional[str]:
        if not text:
            return text
        candidate = text.strip()
        if not candidate:
            return candidate
        lower = candidate.lower()
        contains_accents = any(ord(ch) > 127 for ch in candidate)
        looks_french = contains_accents or any(token in lower for token in FRENCH_HINT_KEYWORDS)
        if not looks_french:
            return candidate
        client = _get_voice_translation_client()
        if not client:
            return candidate
        user_prompt = (
            "Translate the following narrator / voice style hint into concise English instructions suitable for a TTS model. "
            "Preserve age, gender, tone, pacing, personality, and emotional cues. Respond with the translation only."
            f"\n\n{text}"
        )
        try:
            response = client.create_message(
                model=VOICE_TRANSLATION_MODEL,
                system="You are a precise translator who rewrites short voice direction notes into fluent English instructions.",
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0,
                max_tokens=300,
            )
            translated = ""
            if response and getattr(response, "content", None):
                translated = response.content[0].text.strip()  # type: ignore[attr-defined]
            if translated:
                return translated
        except Exception as exc:  # pragma: no cover - translation is best-effort
            logger.warning("Voice hint translation failed: %s", exc)
        return candidate

    def _compose_voice_instructions(
        voice_hint: Optional[str],
        project_summary: str,
        tone: str,
        audience: str,
        language_hint: str,
        scenario_excerpt: str,
    ) -> str:
        normalized_hint = _maybe_translate_voice_hint(voice_hint)
        if normalized_hint:
            return normalized_hint.strip()
        base_voice = f"Use a narrator aligned with a {tone} delivery suitable for a {audience} audience."
        fragments = [
            base_voice,
            f"Speak in {language_hint} with clear articulation, medium pace, natural breathing and pedagogical warmth.",
            f"Audience: {audience}. Maintain the requested tone '{tone}'.",
        ]
        if project_summary:
            fragments.append(f"Project brief: {project_summary}")
        if scenario_excerpt:
            fragments.append(f"Scenario excerpt for context: {scenario_excerpt}")
        return " ".join(fragments).strip()

    def ensure_voice_instructions(project_name: str, scenario_text: str, language_hint: str) -> str:
        profile = load_project_profile(project_name)
        existing = profile.get("voice_instructions")
        source = (profile.get("voice_instructions_source") or "").lower()
        notes = profile.get("project_notes") or "Documentaire historique sur le patrimoine maritime français."
        tone = profile.get("tone") or "narration immersive, empathique et documentée"
        audience = profile.get("audience") or "grand public"
        snippet = "\n".join(scenario_text.strip().split("\n")[:5]).strip()[:600]
        voice_hint, cleaned_notes = _extract_voice_hint(notes)

        if isinstance(existing, str) and existing.strip():
            if source == "manual":
                return existing
            if not voice_hint or voice_hint.lower() in existing.lower():
                return existing

        instructions = _compose_voice_instructions(
            voice_hint,
            cleaned_notes or notes,
            tone,
            audience,
            language_hint,
            snippet,
        )
        upsert_project_config_entry(
            project_name,
            {
                "voice_instructions": instructions,
                "voice_instructions_source": "project_notes" if voice_hint else "auto",
            },
        )
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

    MAX_SCENARIO_IMAGES = 10

    def slides_directory(project_name: str, session_id: str, ensure: bool = False) -> Path:
        path = settings.projects_dir / project_name / "slides" / session_id
        if ensure:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def videos_directory(project_name: str, ensure: bool = False) -> Path:
        path = settings.projects_dir / project_name / "videos"
        if ensure:
            path.mkdir(parents=True, exist_ok=True)
        return path

    async def _process_tts_job(job: TTSJob) -> None:
        session_id = job["session_id"]
        job_id = job["job_id"]
        current_meta = session_store.get_scenario_audio(session_id) or {}
        if current_meta.get("job_id") != job_id:
            return
        running_meta = {
            **current_meta,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
        }
        session_store.save_scenario_audio(session_id, running_meta)
        log_progress(
            "SCENARIO_AUDIO_START",
            session=session_id,
            project=job["project_name"],
            job=job_id,
            provider=job["provider"],
        )
        loop = asyncio.get_running_loop()

        def _run_sync() -> Dict[str, Any]:
            return _execute_tts_job(job)

        try:
            metadata = await loop.run_in_executor(None, _run_sync)
        except Exception as exc:
            log_progress(
                "SCENARIO_AUDIO_FAILED",
                session=session_id,
                project=job["project_name"],
                job=job_id,
                error=str(exc),
            )
            failure_meta = {
                "status": "failed",
                "job_id": job_id,
                "error": str(exc),
                "project": job["project_name"],
                "language": job["language"],
                "requested_at": job["requested_at"],
                "finished_at": datetime.utcnow().isoformat(),
                "tts_provider": job["provider"],
            }
            session_store.save_scenario_audio(session_id, failure_meta)
            return

        latest = session_store.get_scenario_audio(session_id) or {}
        if latest.get("job_id") != job_id:
            return
        metadata["requested_at"] = job["requested_at"]
        metadata["started_at"] = running_meta.get("started_at")
        metadata["finished_at"] = datetime.utcnow().isoformat()
        session_store.save_scenario_audio(session_id, metadata)

        if metadata.get("backgrounds_applied"):
            log_progress(
                "SCENARIO_AUDIO_BACKGROUND_APPLIED",
                session=session_id,
                project=job["project_name"],
                layers=metadata.get("backgrounds_applied"),
            )
        elif metadata.get("background_tracks_requested"):
            log_progress(
                "SCENARIO_AUDIO_BACKGROUND_SKIPPED",
                session=session_id,
                project=job["project_name"],
                reason="mix_failed",
            )

        log_progress(
            "SCENARIO_AUDIO_DONE",
            session=session_id,
            project=job["project_name"],
            job=job_id,
            path=metadata.get("path"),
            duration=metadata.get("num_samples"),
        )

    async def _tts_worker() -> None:
        queue: asyncio.Queue[TTSJob] = app.state.tts_queue
        try:
            while True:
                job = await queue.get()
                await _process_tts_job(job)
        except asyncio.CancelledError:
            logger.info("TTS worker cancelled")
            raise

    def _execute_tts_job(job: TTSJob) -> Dict[str, Any]:
        text = job["text"]
        language = job["language"] or "French"
        project_name = job["project_name"]
        provider = job["provider"] or "qwen"
        voice_id = job.get("voice_id")

        def _synthesize_qwen() -> Dict[str, Any]:
            return text_to_speech_with_instructions(
                text=text,
                project_name=project_name,
                language=language,
            )

        if provider == "elevenlabs":
            if not voice_id:
                raise ValueError("Aucune voix ElevenLabs sélectionnée pour ce projet.")
            result = eleven_labs_tts(
                text=text,
                voice_id=voice_id,
            )
            result.setdefault("sample_rate", 44100)
        else:
            try:
                result = _synthesize_qwen()
            except ValueError as exc:
                message = str(exc)
                lowered = message.lower()
                if any(token in lowered for token in ["aucune voix", "no voice", "voice instructions"]):
                    ensure_voice_instructions(project_name, text, language)
                    result = _synthesize_qwen()
                else:
                    raise
            provider = "qwen"

        voice_path = Path(result["path"])
        (
            layered_path,
            backgrounds_applied,
            dry_voice_path,
            backgrounds_requested,
            background_plan,
        ) = apply_background_selection(voice_path, project_name, text)
        result["path"] = str(layered_path)
        if dry_voice_path:
            result["voice_only_path"] = str(dry_voice_path)
        if background_plan:
            result["background_plan"] = background_plan

        if not result.get("sample_rate") or not result.get("num_samples"):
            try:
                segment = AudioSegment.from_file(layered_path)
                result.setdefault("sample_rate", segment.frame_rate)
                result.setdefault("num_samples", int(segment.frame_count()))
            except Exception:
                pass

        metadata = {
            **result,
            "status": "done",
            "language": language,
            "text_length": len(text),
            "generated_at": datetime.utcnow().isoformat(),
            "backgrounds_applied": backgrounds_applied,
            "background_tracks_requested": backgrounds_requested,
            "tts_provider": provider,
            "job_id": job["job_id"],
        }
        return metadata

    async def _start_tts_worker() -> None:
        if app.state.tts_queue is None:
            app.state.tts_queue = asyncio.Queue()
        if app.state.tts_worker is None:
            app.state.tts_worker = asyncio.create_task(_tts_worker())

    async def _stop_tts_worker() -> None:
        worker = getattr(app.state, "tts_worker", None)
        if worker:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
            app.state.tts_worker = None

    app.add_event_handler("startup", _start_tts_worker)
    app.add_event_handler("shutdown", _stop_tts_worker)

    def project_outputs_directory(project_name: str, ensure: bool = False) -> Path:
        path = settings.projects_dir / project_name / "outputs"
        if ensure:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def restore_session_from_profile(session_payload: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        if not session_payload or not isinstance(profile, dict):
            return session_payload
        updates: Dict[str, Any] = {}
        if profile.get("last_scenarios"):
            updates["scenarios"] = profile["last_scenarios"]
        if profile.get("final_scenario"):
            updates["selected_scenario"] = profile["final_scenario"]
        if profile.get("final_audio"):
            updates["scenario_audio"] = profile["final_audio"]
        if profile.get("final_slideshow"):
            updates["scenario_slideshow"] = profile["final_slideshow"]
        if not updates:
            return session_payload
        return session_store.update_session(session_payload["session_id"], updates)

    def persist_final_assets(project_name: str, session_data: Dict[str, Any]) -> None:
        entry: Dict[str, Any] = {
            "finalized_at": datetime.utcnow().isoformat(),
        }
        if session_data.get("selected_scenario"):
            entry["final_scenario"] = session_data["selected_scenario"]
        outputs_dir = project_outputs_directory(project_name, ensure=True)
        slug = slugify(project_name)
        audio_meta = session_data.get("scenario_audio")
        if audio_meta and audio_meta.get("path"):
            audio_source = Path(audio_meta["path"])
            if not audio_source.is_absolute():
                audio_source = (Path.cwd() / audio_source).resolve()
            if audio_source.exists():
                audio_ext = audio_source.suffix or ".wav"
                final_audio_path = outputs_dir / f"audio_{slug}{audio_ext}"
                if audio_source.resolve() != final_audio_path.resolve():
                    final_audio_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(audio_source, final_audio_path)
                audio_payload = dict(audio_meta)
                audio_payload["path"] = str(final_audio_path)
                entry["final_audio"] = audio_payload
        slideshow_meta = session_data.get("scenario_slideshow")
        if slideshow_meta and slideshow_meta.get("path"):
            video_source = Path(slideshow_meta["path"])
            if not video_source.is_absolute():
                video_source = (Path.cwd() / video_source).resolve()
            if video_source.exists():
                video_ext = video_source.suffix or ".mp4"
                final_video_path = outputs_dir / f"video_{slug}{video_ext}"
                if video_source.resolve() != final_video_path.resolve():
                    final_video_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(video_source, final_video_path)
                video_payload = dict(slideshow_meta)
                video_payload["path"] = str(final_video_path)
                entry["final_slideshow"] = video_payload
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
                        "final_slideshow": profile.get("final_slideshow"),
                    })
        return {"projects": projects}

    @app.get("/projects/{project_name}", tags=["projects"])
    async def get_project_details(project_name: str) -> dict:
        project_dir = settings.projects_dir / project_name
        if not project_dir.exists():
            raise HTTPException(status_code=404, detail="Projet introuvable")
        profile = load_project_profile(project_name)
        if not profile:
            upsert_project_config_entry(project_name, {})
            profile = load_project_profile(project_name)
        if not profile:
            profile = {}
        settings_meta = load_project_settings(project_name)
        audio_selection = load_audio_selection(project_name)
        scenario_config = profile.get("scenario_config") or {}
        gen_params = scenario_config.get("generation_parameters") or {}
        audience_value = profile.get("audience") or (gen_params.get("public_cible") or {}).get("value")
        tone_value = profile.get("tone") or (gen_params.get("ton") or {}).get("value")
        duration_param = gen_params.get("duree") or {}
        target_duration = profile.get("target_duration") or duration_param.get("value") or duration_param.get("default")
        try:
            target_duration = int(target_duration) if target_duration is not None else None
        except (TypeError, ValueError):
            target_duration = None
        preference_options = _get_preference_options()
        return {
            "name": project_name,
            "scenario_target": settings_meta.get("scenario_target", 3),
            "project_notes": profile.get("project_notes"),
            "voice_instructions": profile.get("voice_instructions"),
            "voice_instructions_source": profile.get("voice_instructions_source"),
            "allowed_websites": profile.get("allowed_websites"),
            "audience": audience_value,
            "tone": tone_value,
            "target_duration": target_duration,
            "tts_provider": profile.get("tts_provider", "qwen"),
            "tts_voice_id": profile.get("tts_voice_id"),
            "preference_options": preference_options,
            "last_scenarios": profile.get("last_scenarios") or [],
            "last_scenarios_generated_at": profile.get("last_scenarios_generated_at"),
            "final_scenario": profile.get("final_scenario"),
            "final_audio": profile.get("final_audio"),
            "final_slideshow": profile.get("final_slideshow"),
            "audio_selection": audio_selection,
        }

    @app.post("/sessions", tags=["sessions"])
    async def create_session(payload: SessionCreateRequest) -> dict:
        automation_runner.ensure_project_exists(payload.project_name)
        settings_meta = load_project_settings(payload.project_name)
        target = payload.scenario_target or settings_meta.get("scenario_target", 3)
        session = session_store.create_session(payload.project_name, payload.initial_step, scenario_target=target)
        profile = load_project_profile(payload.project_name)
        if profile:
            session = restore_session_from_profile(session, profile)
        else:
            session = session_store.load_session(session["session_id"]) or session
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

        # Retrieve audio transcriptions from Parquet storage.
        # A retry loop handles the case where the user triggers generation
        # while an audio upload/transcription is still in progress.
        audio_transcriptions = fetch_project_transcriptions(project_name)
        if not audio_transcriptions and voices:
            import time as _time
            max_retries, wait_seconds = 3, 5
            for attempt in range(1, max_retries + 1):
                logger.info(
                    "No transcriptions yet but %d voice(s) selected — "
                    "waiting %ds for pending transcriptions (attempt %d/%d)",
                    len(voices), wait_seconds, attempt, max_retries,
                )
                await asyncio.sleep(wait_seconds)
                audio_transcriptions = fetch_project_transcriptions(project_name)
                if audio_transcriptions:
                    logger.info(
                        "Transcriptions now available: %d (after %d retries)",
                        len(audio_transcriptions), attempt,
                    )
                    break
            if not audio_transcriptions:
                logger.warning(
                    "⚠️  %d voice file(s) selected but 0 transcriptions found "
                    "after %d retries. Scenarios will be generated without "
                    "audio transcription context.",
                    len(voices), max_retries,
                )

        # Load project notes and enrich the prompt
        project_profile = load_project_profile(project_name)
        project_notes = project_profile.get("project_notes", "")
        constraints = build_project_constraints(project_profile)
        
        # Enrich prompt with project context if notes exist
        enriched_prompt = req.prompt
        if project_notes and project_notes.strip():
            if enriched_prompt and enriched_prompt.strip():
                enriched_prompt = f"{project_notes}\n\n{enriched_prompt}"
            else:
                enriched_prompt = project_notes
        constraint_prompt = build_constraint_prompt_block(constraints)
        if constraint_prompt:
            if enriched_prompt and enriched_prompt.strip():
                enriched_prompt = f"{constraint_prompt}\n\n{enriched_prompt}"
            else:
                enriched_prompt = constraint_prompt

        # Resolve LLM model for scenario generation
        resolved_model = resolve_model_id(req.model_id)
        config_overrides = build_config_overrides_from_constraints(constraints)

        params = {
            "prompt": enriched_prompt,
            "mode": req.mode,
            "output_dir": req.output_dir,
            "scenario_target": req.scenario_target or session.get("scenario_target", 3),
            "audio_transcriptions": audio_transcriptions,
            "model_id": resolved_model,
            "tts_provider": project_profile.get("tts_provider", "qwen"),
        }
        if config_overrides:
            params["config_overrides"] = config_overrides
        log_progress(
            "SCENARIO_GENERATE_START",
            session=req.session_id,
            project=project_name,
            target=params["scenario_target"],
            transcriptions=len(audio_transcriptions),
            model=resolved_model,
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

            async def regenerate_single_scenario(target_index: int) -> Optional[dict]:
                rerun_params = dict(params)
                rerun_params["scenario_target"] = 1
                rerun_output_dir = Path(req.output_dir or "./output")
                rerun_params["output_dir"] = str(
                    (rerun_output_dir / f"scenario_rerun_{target_index}_{uuid4().hex[:4]}").resolve()
                )
                rerun_result = await loop.run_in_executor(None, lambda: scenario_skill.run(rerun_params))
                rerun_scenarios = rerun_result.get("scenarios", [])
                if not rerun_scenarios:
                    return None
                cloned = dict(rerun_scenarios[0])
                cloned.setdefault("scenario_index", target_index)
                return cloned

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

            failing_indexes: List[int] = []
            if constraints.get("has_requirements"):
                for entry in prepared_scenarios:
                    report = assess_scenario_compliance(entry, constraints)
                    entry["compliance_report"] = report
                    idx = entry.get("scenario_index")
                    if idx is not None and not report["is_compliant"]:
                        failing_indexes.append(idx)
            else:
                for entry in prepared_scenarios:
                    entry["compliance_report"] = {"is_compliant": True, "issues": []}

            if failing_indexes:
                target_idx = next((idx for idx in failing_indexes if isinstance(idx, int)), None)
                if target_idx is not None:
                    log_progress(
                        "SCENARIO_RERUN_START",
                        session=req.session_id,
                        project=project_name,
                        scenario_index=target_idx,
                    )
                    replacement = await regenerate_single_scenario(target_idx)
                    if replacement:
                        replacement_report = assess_scenario_compliance(replacement, constraints)
                        replacement["compliance_report"] = replacement_report
                        if replacement_report["is_compliant"]:
                            for idx_entry, entry in enumerate(prepared_scenarios):
                                if entry.get("scenario_index") == target_idx:
                                    prepared_scenarios[idx_entry] = replacement
                                    break
                            log_progress(
                                "SCENARIO_RERUN_DONE",
                                session=req.session_id,
                                project=project_name,
                                scenario_index=target_idx,
                            )
                        else:
                            issues = "; ".join(replacement_report["issues"])
                            log_progress(
                                "SCENARIO_RERUN_FAILED",
                                session=req.session_id,
                                project=project_name,
                                scenario_index=target_idx,
                                reason=f"non_compliant_replacement: {issues}",
                            )
                    else:
                        log_progress(
                            "SCENARIO_RERUN_FAILED",
                            session=req.session_id,
                            project=project_name,
                            scenario_index=target_idx,
                            reason="no_scenario_generated",
                        )

            ranking_order = compute_scenario_ranking(result.get("config"), prepared_scenarios, project_name)
            if ranking_order:
                rank_map = {idx: position + 1 for position, idx in enumerate(ranking_order)}
                for entry in prepared_scenarios:
                    idx = entry.get("scenario_index")
                    if idx is None:
                        continue
                    rank_value = rank_map.get(idx)
                    if rank_value is None:
                        continue
                    entry["quality_rank"] = rank_value
                    payload = entry.get("scenario")
                    if isinstance(payload, dict):
                        payload["quality_rank"] = rank_value
                prepared_scenarios.sort(
                    key=lambda item: (
                        item.get("quality_rank")
                        if item.get("quality_rank") is not None
                        else item.get("scenario_index") or 0
                    )
                )

            session_store.update_session(req.session_id, {"scenarios": prepared_scenarios})
            upsert_project_config_entry(
                project_name,
                {
                    "last_scenarios": prepared_scenarios,
                    "last_scenarios_generated_at": datetime.utcnow().isoformat(),
                },
            )
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
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        scenarios = session.get("scenarios") or []
        if not scenarios:
            profile = load_project_profile(session["project_name"])
            fallback = profile.get("last_scenarios")
            if not fallback and profile.get("final_scenario"):
                fallback = [profile["final_scenario"]]
            if fallback:
                session_store.update_session(session_id, {"scenarios": fallback})
                scenarios = fallback
        return {"scenarios": scenarios}

    @app.get("/sessions/{session_id}/scenario-selection", response_model=ScenarioSelectionResponse, tags=["sessions"])
    async def get_selected_scenario(session_id: str) -> ScenarioSelectionResponse:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        selected = session.get("selected_scenario")
        if not selected:
            profile = load_project_profile(session["project_name"])
            selected = profile.get("final_scenario")
            if selected:
                session_store.update_session(session_id, {"selected_scenario": selected})
        return ScenarioSelectionResponse(scenario=selected)

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
            profile = load_project_profile(session["project_name"])
            metadata = profile.get("final_audio")
            if metadata:
                session_store.save_scenario_audio(session_id, metadata)
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
        profile = load_project_profile(session["project_name"])
        provider = (profile.get("tts_provider") or "qwen").lower()
        voice_id = profile.get("tts_voice_id")
        if provider == "elevenlabs" and not voice_id:
            raise HTTPException(
                status_code=400,
                detail="Sélectionnez une voix ElevenLabs avant de générer l'audio."
            )
        language = payload.language or "French"
        job_id = uuid4().hex
        requested_at = datetime.utcnow().isoformat()
        metadata = {
            "status": "pending",
            "job_id": job_id,
            "language": language,
            "text_length": len(text),
            "requested_at": requested_at,
            "tts_provider": provider,
        }
        session_store.save_scenario_audio(session_id, metadata)
        queue: asyncio.Queue = getattr(app.state, "tts_queue", None)
        if queue is None:
            app.state.tts_queue = asyncio.Queue()
            queue = app.state.tts_queue
            if getattr(app.state, "tts_worker", None) is None:
                app.state.tts_worker = asyncio.create_task(_tts_worker())
        job: TTSJob = {
            "job_id": job_id,
            "session_id": session_id,
            "project_name": session["project_name"],
            "text": text,
            "language": language,
            "provider": provider,
            "voice_id": voice_id,
            "requested_at": requested_at,
        }
        await queue.put(job)
        log_progress(
            "SCENARIO_AUDIO_QUEUED",
            session=session_id,
            project=session["project_name"],
            job=job_id,
            provider=provider,
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

    def _serialize_image_entry(session_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(entry)
        data["download_url"] = f"/sessions/{session_id}/scenario-images/{entry['id']}"
        return data

    @app.get("/sessions/{session_id}/scenario-images", tags=["sessions"])
    async def list_scenario_images(session_id: str) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        images = session.get("scenario_images", [])
        return {"images": [_serialize_image_entry(session_id, img) for img in images]}

    @app.post("/sessions/{session_id}/scenario-images", tags=["sessions"])
    async def upload_scenario_image(session_id: str, file: UploadFile = File(...)) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        images = list(session.get("scenario_images", []))
        if len(images) >= MAX_SCENARIO_IMAGES:
            raise HTTPException(status_code=400, detail="Nombre maximal d'images atteint (10).")
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Fichier vide.")
        ext = Path(file.filename).suffix.lower() or ".jpg"
        allowed_ext = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"}
        if ext not in allowed_ext:
            ext = ".jpg"
        project_name = session["project_name"]
        directory = slides_directory(project_name, session_id, ensure=True)
        image_id = uuid4().hex
        filename = f"{image_id}{ext}"
        target = directory / filename
        with open(target, "wb") as f:
            f.write(contents)
        metadata = {
            "id": image_id,
            "filename": filename,
            "original_name": file.filename,
            "uploaded_at": datetime.utcnow().isoformat(),
            "size": len(contents),
        }
        images.append(metadata)
        session_store.update_session(session_id, {"scenario_images": images})
        log_progress(
            "SCENARIO_IMAGE_ADDED",
            session=session_id,
            project=project_name,
            image=image_id,
        )
        return {"image": _serialize_image_entry(session_id, metadata)}

    @app.post("/sessions/{session_id}/scenario-images/reorder", tags=["sessions"])
    async def reorder_scenario_images(session_id: str, payload: ImageOrderPayload):
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        images = session.get("scenario_images", [])
        mapping = {img["id"]: img for img in images}
        new_list: List[Dict[str, Any]] = []
        for image_id in payload.order:
            img = mapping.get(image_id)
            if img:
                new_list.append(img)
        for image in images:
            if image["id"] not in payload.order:
                new_list.append(image)
        session_store.update_session(session_id, {"scenario_images": new_list})
        return {"images": [_serialize_image_entry(session_id, img) for img in new_list]}

    @app.delete("/sessions/{session_id}/scenario-images/{image_id}", tags=["sessions"])
    async def delete_scenario_image(session_id: str, image_id: str):
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        images = list(session.get("scenario_images", []))
        project_name = session["project_name"]
        directory = slides_directory(project_name, session_id, ensure=False)
        removed = None
        remaining: List[Dict[str, Any]] = []
        for image in images:
            if image["id"] == image_id:
                removed = image
            else:
                remaining.append(image)
        if not removed:
            raise HTTPException(status_code=404, detail="Image introuvable")
        if directory.exists():
            target = directory / removed["filename"]
            if target.exists():
                target.unlink()
        session_store.update_session(session_id, {"scenario_images": remaining})
        log_progress(
            "SCENARIO_IMAGE_REMOVED",
            session=session_id,
            project=project_name,
            image=image_id,
        )
        return {"status": "deleted"}

    @app.get("/sessions/{session_id}/scenario-images/{image_id}", tags=["sessions"])
    async def stream_scenario_image(session_id: str, image_id: str):
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        project_name = session["project_name"]
        directory = slides_directory(project_name, session_id, ensure=False)
        for image in session.get("scenario_images", []):
            if image["id"] == image_id:
                target = directory / image["filename"]
                if not target.exists():
                    raise HTTPException(status_code=404, detail="Fichier image introuvable")
                return FileResponse(target)
        raise HTTPException(status_code=404, detail="Image introuvable")

    @app.get("/sessions/{session_id}/slideshow", tags=["sessions"])
    async def get_slideshow_metadata(session_id: str) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        metadata = session.get("scenario_slideshow")
        if not metadata:
            profile = load_project_profile(session["project_name"])
            metadata = profile.get("final_slideshow")
            if metadata:
                session_store.update_session(session_id, {"scenario_slideshow": metadata})
        if not metadata:
            raise HTTPException(status_code=404, detail="Aucun diaporama généré")
        return metadata

    @app.get("/sessions/{session_id}/slideshow/file", tags=["sessions"])
    async def stream_slideshow(session_id: str):
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        metadata = session.get("scenario_slideshow")
        if not metadata or not metadata.get("path"):
            profile = load_project_profile(session["project_name"])
            metadata = profile.get("final_slideshow")
            if metadata:
                session_store.update_session(session_id, {"scenario_slideshow": metadata})
        if not metadata or not metadata.get("path"):
            raise HTTPException(status_code=404, detail="Aucun diaporama généré")
        path_value = metadata["path"]
        video_path = Path(path_value)
        if not video_path.is_absolute():
            video_path = (Path.cwd() / video_path).resolve()
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Fichier vidéo introuvable")
        return FileResponse(video_path)

    @app.post("/sessions/{session_id}/slideshow", tags=["sessions"])
    async def create_slideshow(session_id: str) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        project_name = session["project_name"]
        images = session.get("scenario_images", [])
        if not images:
            log_progress(
                "SCENARIO_SLIDESHOW_FAILED",
                session=session_id,
                project=project_name,
                reason="no_images",
            )
            raise HTTPException(status_code=400, detail="Ajoutez des images avant de créer un diaporama.")
        audio = session.get("scenario_audio")
        if not audio or not audio.get("path"):
            log_progress(
                "SCENARIO_SLIDESHOW_FAILED",
                session=session_id,
                project=project_name,
                reason="no_audio",
            )
            raise HTTPException(status_code=400, detail="Aucun audio disponible pour accompagner le diaporama.")
        slides_dir = slides_directory(project_name, session_id, ensure=True)
        audio_path = Path(audio["path"])
        if not audio_path.is_absolute():
            audio_path = (Path.cwd() / audio_path).resolve()
        if not audio_path.exists():
            log_progress(
                "SCENARIO_SLIDESHOW_FAILED",
                session=session_id,
                project=project_name,
                reason="audio_file_missing",
                path=str(audio_path),
            )
            raise HTTPException(status_code=404, detail="Fichier audio introuvable pour le diaporama.")
        output_dir = videos_directory(project_name, ensure=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        output_path = output_dir / f"{session_id}_{timestamp}.mp4"
        try:
            generated_path = slideshow(str(slides_dir), str(audio_path), str(output_path))
        except Exception as exc:
            logger.exception("Slideshow generation failed for session %s", session_id)
            log_progress(
                "SCENARIO_SLIDESHOW_FAILED",
                session=session_id,
                project=project_name,
                reason="render_error",
                error=str(exc),
            )
            raise HTTPException(status_code=500, detail=f"Impossible de créer le diaporama: {exc}") from exc
        metadata = {
            "status": "generated",
            "path": generated_path,
            "created_at": datetime.utcnow().isoformat(),
            "image_count": len(images),
        }
        session_store.update_session(session_id, {"scenario_slideshow": metadata})
        log_progress(
            "SCENARIO_SLIDESHOW_DONE",
            session=session_id,
            project=project_name,
            path=generated_path,
        )
        return metadata

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

    @app.get("/projects/{project_name}/slideshow", tags=["projects"])
    async def stream_project_slideshow(project_name: str):
        profile = load_project_profile(project_name)
        metadata = profile.get("final_slideshow")
        if not metadata or not metadata.get("path"):
            raise HTTPException(status_code=404, detail="Aucune vidéo finale pour ce projet")
        video_path = Path(metadata["path"])
        if not video_path.is_absolute():
            video_path = (Path.cwd() / video_path).resolve()
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Fichier vidéo introuvable")
        return FileResponse(video_path)

    @app.get("/sessions/{session_id}/audio-selection", tags=["sessions"])
    async def get_audio_selection(session_id: str) -> dict:
        session = session_store.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        selection = load_audio_selection(session["project_name"])
        profile = load_project_profile(session["project_name"])
        provider = profile.get("tts_provider", "qwen")
        selection["tts_provider"] = provider
        if provider == "elevenlabs":
            if profile.get("tts_voice_id"):
                selection["tts_voice_id"] = profile.get("tts_voice_id")
        else:
            selection["tts_voice_id"] = None
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
        selection_payload: Dict[str, Any] = {"voices": voices, "backgrounds": backgrounds}
        if payload.tts_voice_id:
            selection_payload["tts_voice_id"] = payload.tts_voice_id.strip()
        saved = save_audio_selection(payload.project_name, selection_payload)
        if payload.tts_voice_id:
            upsert_project_config_entry(
                payload.project_name,
                {
                    "tts_voice_id": payload.tts_voice_id.strip(),
                },
            )
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
        index_file = (frontend_dir / "index.html").resolve()

        @app.get("/", include_in_schema=False)
        async def serve_frontend_root():
            if index_file.exists():
                return FileResponse(index_file)
            raise HTTPException(status_code=404, detail="Frontend not built")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_frontend(full_path: str):
            candidate = (frontend_dir / full_path).resolve()
            try:
                candidate.relative_to(frontend_dir.resolve())
            except ValueError:
                raise HTTPException(status_code=403, detail="Chemin invalide")
            if candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
            if index_file.exists():
                return FileResponse(index_file)
            raise HTTPException(status_code=404, detail="Asset not found")

    return app
