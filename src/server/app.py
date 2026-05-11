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
from typing import Any, Dict, List, Optional, Tuple, TypedDict
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Query, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
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
from memoiredesterritoires.transcription.transcription_sum import summarize_transcript_robust
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
    get_project_audio_file,
)
from pydub import AudioSegment

# ---------------------------------------------------------------------------
# Monkey-patch pydub to use the imageio-ffmpeg bundled binary instead of
# requiring system-level ffmpeg / ffprobe (which may not be on PATH on Windows).
# Must run AFTER pydub is imported so that pydub.audio_segment has already
# created its local reference to mediainfo_json.
# ---------------------------------------------------------------------------
def _setup_pydub_ffmpeg() -> None:
    """Redirect pydub's ffmpeg/ffprobe calls to the imageio-ffmpeg binary."""
    import subprocess
    import pydub.utils
    import pydub.audio_segment as _pydub_as

    try:
        import imageio_ffmpeg  # type: ignore
        _ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return  # imageio-ffmpeg not available — leave pydub as-is

    # 1. Patch pydub.utils.which so ffmpeg/ffprobe both resolve to our binary
    _orig_which = pydub.utils.which

    def _patched_which(name: str):
        if name in ("ffmpeg", "avconv", "ffprobe", "avprobe"):
            return _ffmpeg_bin
        return _orig_which(name)

    pydub.utils.which = _patched_which

    # 2. Set the converter attribute used when spawning the decoder process
    _pydub_as.AudioSegment.converter = _ffmpeg_bin

    # 3. Replace mediainfo_json with a version that uses "ffmpeg -i" stderr
    #    (imageio-ffmpeg ships only ffmpeg.exe, not ffprobe.exe)
    def _mediainfo_json(filepath, read_ahead_limit=-1):  # noqa: ARG001
        import os, re
        try:
            proc = subprocess.run(
                [_ffmpeg_bin, "-v", "quiet", "-i", str(filepath)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stderr = proc.stderr.decode("utf-8", errors="replace")
        except Exception:
            stderr = ""

        # Duration: "Duration: HH:MM:SS.ss"
        duration_s = 0.0
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
        if m:
            duration_s = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

        # Audio stream: "Audio: codec, RATE Hz, stereo|mono|N channels"
        sample_rate = 44100
        channels = 1
        codec_name = "mp3"
        m = re.search(
            r"Audio:\s*(\S+?)(?:,\s*|\s+)(\d+)\s*[Hh]z[^,]*,\s*(?:(stereo|mono)|(\d+)\s*channels?)",
            stderr,
        )
        if m:
            codec_name = m.group(1).rstrip(",")
            sample_rate = int(m.group(2))
            if m.group(3) == "stereo":
                channels = 2
            elif m.group(3) == "mono":
                channels = 1
            elif m.group(4):
                channels = int(m.group(4))

        # Bitrate
        bit_rate = 0
        m = re.search(r"bitrate:\s*(\d+)\s*kb/s", stderr)
        if m:
            bit_rate = int(m.group(1)) * 1000

        file_size = 0
        try:
            file_size = os.path.getsize(str(filepath))
        except Exception:
            pass

        return {
            "format": {
                "filename": str(filepath),
                "duration": str(duration_s),
                "size": str(file_size),
                "format_name": codec_name,
                "format_long_name": codec_name,
                "bit_rate": str(bit_rate),
                "probe_score": 51,
            },
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": codec_name,
                    "sample_rate": str(sample_rate),
                    "channels": int(channels),
                    "bits_per_sample": 16,  # pydub builds "pcm_s{bits_per_sample}le" → must be 16
                    "sample_fmt": "s16",
                }
            ],
        }

    pydub.utils.mediainfo_json = _mediainfo_json
    _pydub_as.mediainfo_json = _mediainfo_json  # local ref inside audio_segment module


_setup_pydub_ffmpeg()
# ---------------------------------------------------------------------------

from .config import AppSettings, get_settings
from .session_store import SessionStore
from .step_config import StepConfigRegistry
from .automation import AutomationRunner
from .chat_agent import ChatAgent
from .audio_validation import validate_audio_file
from utils.claude_client import ClaudeClient

from config.model_registry import get_available_models, resolve_model_id

logger = logging.getLogger(__name__)

# Sentinel written by docker-entrypoint.sh once the Qwen TTS model download finishes.
_QWEN_TTS_LOCAL_DIR = Path(os.getenv("QWEN_TTS_LOCAL_DIR", "models/qwen3-tts"))
_TTS_READY_FILE = _QWEN_TTS_LOCAL_DIR / ".ready"


def _tts_model_ready() -> bool:
    """Return True when the TTS model has been fully downloaded."""
    return _TTS_READY_FILE.exists()

SCENARIO_DEFAULT_CONFIG_PATH = Path(os.getenv("SCENARIO_DEFAULT_CONFIG", "config/default_config.json")).expanduser()
PUNCTUAL_GAIN_DB = -24.0
AMBIENT_GAIN_DB = -30.0
BACKGROUND_PLAN_MODEL = os.getenv("BACKGROUND_PLAN_MODEL", "anthropic/claude-sonnet-4-5")
VOICE_TRANSLATION_MODEL = os.getenv("VOICE_TRANSLATION_MODEL", "anthropic/claude-3-haiku-20240307")
PUNCTUAL_MIN_DURATION = 6.0
PUNCTUAL_MAX_DURATION = 10.0
PUNCTUAL_GAP_SECONDS = 1.0
PUNCTUAL_START_MIN = 3.0
PUNCTUAL_END_PADDING = 5.0
AMBIENT_START_OFFSET = 4.0
AMBIENT_END_PADDING = 5.0
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
VOICE_PREVIEW_TEXT = (
    "Imaginez la Loire en 1950. Les chantiers navals de Nantes bourdonnaient d'activité. "
    "Des coques immenses prenaient forme sous les mains expertes des soudeurs et des "
    "charpentiers. Le Paquebot France, fierté nationale, est né ici en 1960, 106 000 tonnes "
    "de rêves et d'acier. Aujourd'hui, seules les grues jaunes témoignent de ce passé glorieux."
)
ELEVENLABS_DEFAULT_VOICE_IDS = [
    "5l4ttmr4SKNgi0HnOelT",
    "flHkNRp1BlvT73UL6gyz",
    "jK7dAsiVAhbApIS8KkWB",
    "NOpBlnGInO9m6vDvFkFC",
    "jUHQdLfy668sllNiNTSW",
    "tKaoyJLW05zqV0tIH9FD",
    "T4BwQ2ZwlS2BbHIfci4H",
    "GYzIdoKkRyANjBvkKYfO",
    "TojRWZatQyy9dujEdiQ1",
]


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


def _extract_json_object(payload: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(payload)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]+\}", payload)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def _voice_preview_directory(settings: AppSettings) -> Path:
    return (Path.cwd() / settings.data_dir / "generated_speech" / "voice_previews").resolve()


def _voice_preview_path(settings: AppSettings, voice_id: str) -> Path:
    normalized = voice_id.strip()
    if not normalized:
        raise ValueError("voice_id must not be empty")
    preview_root = _voice_preview_directory(settings)
    preview_root.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", normalized)
    return preview_root / f"{safe_name}.mp3"


async def _ensure_voice_preview_file(settings: AppSettings, voice_id: str) -> Path:
    preview_path = _voice_preview_path(settings, voice_id)
    if preview_path.exists():
        return preview_path
    loop = asyncio.get_running_loop()

    def _generate() -> None:
        eleven_labs_tts(
            text=VOICE_PREVIEW_TEXT,
            voice_id=voice_id.strip(),
            output_path=str(preview_path),
        )

    try:
        await loop.run_in_executor(None, _generate)
        log_progress(
            "TTS_PREVIEW_GENERATED",
            voice=voice_id,
            path=str(preview_path),
        )
    except Exception:
        if preview_path.exists():
            try:
                preview_path.unlink()
            except OSError:
                pass
        raise
    return preview_path


def _match_background_choice(choice: Optional[str], candidates: List[str]) -> Optional[str]:
    if not choice:
        return None
    normalized = choice.strip()
    if not normalized:
        return None
    for candidate in candidates:
        if normalized == candidate:
            return candidate
        if normalized == Path(candidate).name:
            return candidate
    return None


def _fallback_mix_plan(
    duration_seconds: float,
    ambient_path: Optional[str],
    punctual_paths: List[str],
) -> Dict[str, Any]:
    plan: Dict[str, Any] = {"ambient": None, "punctual": []}
    if duration_seconds <= 0:
        return plan

    if ambient_path and duration_seconds > (AMBIENT_START_OFFSET + AMBIENT_END_PADDING + 1.0):
        start = max(0.0, min(AMBIENT_START_OFFSET, duration_seconds - AMBIENT_END_PADDING - 1.0))
        end = max(start + PUNCTUAL_MIN_DURATION, duration_seconds - AMBIENT_END_PADDING)
        end = min(end, max(start + 1.0, duration_seconds - 0.2))
        plan["ambient"] = {
            "file": ambient_path,
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
            "gain_db": AMBIENT_GAIN_DB,
            "note": "Fallback fond continu",
        }

    window = max(0.0, duration_seconds - (PUNCTUAL_START_MIN + PUNCTUAL_END_PADDING))
    if not punctual_paths or window <= PUNCTUAL_MIN_DURATION:
        return plan

    spacing = window / (len(punctual_paths) + 1)
    slot_duration = min(
        PUNCTUAL_MAX_DURATION,
        max(PUNCTUAL_MIN_DURATION, duration_seconds * 0.08),
    )
    last_end = 0.0
    for idx, path in enumerate(punctual_paths):
        start = PUNCTUAL_START_MIN + spacing * (idx + 1) - slot_duration / 2
        start = max(PUNCTUAL_START_MIN, start)
        max_start = max(PUNCTUAL_START_MIN, duration_seconds - PUNCTUAL_END_PADDING - slot_duration)
        start = min(start, max_start)
        if start < last_end + PUNCTUAL_GAP_SECONDS:
            start = last_end + PUNCTUAL_GAP_SECONDS
        if start + slot_duration > duration_seconds - 0.2:
            break
        last_end = start + slot_duration
        plan["punctual"].append(
            {
                "file": path,
                "start_seconds": round(start, 3),
                "duration_seconds": round(slot_duration, 3),
                "gain_db": PUNCTUAL_GAIN_DB,
                "note": "Fallback son ponctuel",
            }
        )
    return plan


def _sanitize_mix_plan(
    raw_plan: Dict[str, Any],
    duration_seconds: float,
    ambient_path: Optional[str],
    punctual_paths: List[str],
) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {"ambient": None, "punctual": []}
    if duration_seconds <= 0:
        return sanitized

    ambient_data = raw_plan.get("fond_continu") or raw_plan.get("ambient")
    ambient_options = [ambient_path] if ambient_path else []
    if isinstance(ambient_data, dict) and ambient_options:
        matched = _match_background_choice(ambient_data.get("file"), ambient_options)
        if matched:
            try:
                start = float(ambient_data.get("start_seconds", AMBIENT_START_OFFSET))
            except (TypeError, ValueError):
                start = AMBIENT_START_OFFSET
            try:
                end = float(ambient_data.get("end_seconds", 0.0))
            except (TypeError, ValueError):
                end = 0.0
            if end <= 0:
                try:
                    duration_value = float(ambient_data.get("duration_seconds", 0.0))
                except (TypeError, ValueError):
                    duration_value = 0.0
                end = start + max(duration_value, duration_seconds - AMBIENT_END_PADDING - start)
            start = max(0.0, min(start, max(0.0, duration_seconds - 1.0)))
            end = min(max(start + 1.0, end), duration_seconds - 0.1)
            try:
                gain = float(ambient_data.get("gain_db", AMBIENT_GAIN_DB))
            except (TypeError, ValueError):
                gain = AMBIENT_GAIN_DB
            note = ambient_data.get("note")
            sanitized["ambient"] = {
                "file": matched,
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "gain_db": gain,
                "note": note.strip() if isinstance(note, str) else None,
            }

    raw_punctual = raw_plan.get("sons_ponctuels") or raw_plan.get("punctual") or raw_plan.get("sons")
    if isinstance(raw_punctual, list):
        last_end = 0.0
        used_files: set[str] = set()
        for entry in sorted(raw_punctual, key=lambda item: float(item.get("start_seconds", 0.0))):
            if len(sanitized["punctual"]) >= len(punctual_paths):
                break
            if not isinstance(entry, dict):
                continue
            matched = _match_background_choice(entry.get("file"), punctual_paths)
            if not matched or matched in used_files:
                continue
            try:
                start = float(entry.get("start_seconds", PUNCTUAL_START_MIN))
            except (TypeError, ValueError):
                start = PUNCTUAL_START_MIN
            try:
                duration = float(entry.get("duration_seconds", PUNCTUAL_MIN_DURATION))
            except (TypeError, ValueError):
                duration = PUNCTUAL_MIN_DURATION
            duration = max(PUNCTUAL_MIN_DURATION, min(PUNCTUAL_MAX_DURATION, duration))
            start = max(PUNCTUAL_START_MIN, start)
            max_start = max(PUNCTUAL_START_MIN, duration_seconds - PUNCTUAL_END_PADDING - duration)
            start = min(start, max_start)
            if start < last_end + PUNCTUAL_GAP_SECONDS:
                start = last_end + PUNCTUAL_GAP_SECONDS
            if start + duration > duration_seconds - 0.1:
                continue
            try:
                gain = float(entry.get("gain_db", PUNCTUAL_GAIN_DB))
            except (TypeError, ValueError):
                gain = PUNCTUAL_GAIN_DB
            note = entry.get("note") or entry.get("commentaire")
            sanitized["punctual"].append(
                {
                    "file": matched,
                    "start_seconds": round(start, 3),
                    "duration_seconds": round(duration, 3),
                    "gain_db": gain,
                    "note": note.strip() if isinstance(note, str) else None,
                }
            )
            used_files.add(matched)
            last_end = start + duration

    return sanitized


def _build_background_prompt(
    voice_path: Path,
    duration_seconds: float,
    scenario_excerpt: str,
    ambient_path: Optional[str],
    punctual_paths: List[str],
) -> str:
    try:
        voice_display = voice_path.relative_to(Path.cwd())
    except ValueError:
        voice_display = voice_path
    lines = [
        "Tu dois créer un mix audio professionnel pour créer une ambiance audio immersive. Voici les instructions détaillées :",
        f"Durée approximative de la voix : {duration_seconds:.1f} secondes.",
        "",
        "**Fichiers sources :**",
        f"- Voix : {voice_display}",
    ]
    if ambient_path:
        lines.append(f"- Fond continu potentiel : {ambient_path}")
    if punctual_paths:
        lines.append("**Sons ponctuels disponibles (copie exactement les chemins ci-dessous) :**")
        for path in punctual_paths:
            lines.append(f"- {path}")
    if scenario_excerpt:
        lines.append("")
        lines.append("**Extrait de la narration :**")
        lines.append(scenario_excerpt)

    if punctual_paths:
        lines.append("")
        lines.append("**Étape 1 — Sons ponctuels :**")
        lines.append("Sélectionne des sons ponctuels et variés parmi la liste fournie.")
        lines.append("- Durée : entre 6 et 10 secondes")
        lines.append("- Volume : 20 dB en dessous de la voix")
        lines.append("- Placement : après 3 s et au plus tard 5 s avant la fin, sans chevauchement, espacé d'au moins 1 s")
        lines.append("- Répartis-les entre début / milieu / fin en fonction du récit.")

    if ambient_path:
        lines.append("")
        lines.append("**Étape 2 — Fond continu :**")
        lines.append(" Choisi dans un son riche qui servira de fond continu pour l'audio afin de renforcer l'immersion.")
        lines.append("- Démarre à 4 s")
        lines.append("- Termine 5 s avant la fin de la narration")
        lines.append("- Volume : 20 dB en dessous de la voix")

    lines.append("")
    lines.append("**Contraintes :**")
    lines.append("- N'invente aucun autre fichier audio.")
    lines.append("- Si un type n'est pas disponible, retourne null ou une liste vide pour ce type.")
    lines.append("- Ne renvoie que la structure JSON.")

    lines.append("")
    lines.append("**Format de réponse (JSON strict) :**")
    lines.append("{")
    lines.append('  "fond_continu": {')
    lines.append('    "file": "chemin_exact",')
    lines.append('    "start_seconds": 4.0,')
    lines.append('    "end_seconds": 120.0,')
    lines.append('    "gain_db": -20,')
    lines.append('    "note": "raison du placement"')
    lines.append("  } ou null,")
    lines.append('  "sons_ponctuels": [')
    lines.append("    {")
    lines.append('      "file": "chemin_exact",')
    lines.append('      "start_seconds": 9.5,')
    lines.append('      "duration_seconds": 8.0,')
    lines.append('      "gain_db": -20,')
    lines.append('      "note": "moment clé de l\'histoire"')
    lines.append("    }")
    lines.append("  ]")
    lines.append("}")
    return "\n".join(lines)


def _summarize_background_plan(plan: Dict[str, Any]) -> Tuple[str, str]:
    ambient = plan.get("ambient")
    ambient_summary = "none"
    if isinstance(ambient, dict):
        ambient_summary = (
            f"{ambient.get('file')}@{ambient.get('start_seconds')}s→{ambient.get('end_seconds')}s "
            f"({ambient.get('gain_db')} dB)"
        )
    punctual_summary = "none"
    punctual_entries = plan.get("punctual") or []
    if isinstance(punctual_entries, list) and punctual_entries:
        parts: List[str] = []
        for entry in punctual_entries:
            if not isinstance(entry, dict):
                continue
            parts.append(
                f"{entry.get('file')}@{entry.get('start_seconds')}s+{entry.get('duration_seconds')}s "
                f"({entry.get('gain_db')} dB)"
            )
        if parts:
            punctual_summary = "; ".join(parts)
    return ambient_summary, punctual_summary


def build_background_mix_plan(
    scenario_text: Optional[str],
    voice_path: Path,
    duration_seconds: float,
    ambient_path: Optional[str],
    punctual_paths: List[str],
) -> Dict[str, Any]:
    if (not ambient_path and not punctual_paths) or duration_seconds <= 1.0:
        return {"ambient": None, "punctual": []}

    scenario_excerpt = ""
    if scenario_text:
        scenario_excerpt = re.sub(r"\s+", " ", scenario_text).strip()
        max_chars = 1500
        if len(scenario_excerpt) > max_chars:
            scenario_excerpt = scenario_excerpt[:max_chars] + "…"

    raw_plan: Dict[str, Any] = {}
    llm_attempted = False
    client = _get_background_plan_client()
    if client and (ambient_path or punctual_paths):
        llm_attempted = True
        user_prompt = _build_background_prompt(
            voice_path=voice_path,
            duration_seconds=duration_seconds,
            scenario_excerpt=scenario_excerpt,
            ambient_path=ambient_path,
            punctual_paths=punctual_paths,
        )
        try:
            response = client.create_message(
                model=BACKGROUND_PLAN_MODEL,
                system="Tu es un ingénieur du son spécialisé dans les ambiances industrielles.",
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.2,
                max_tokens=800,
            )
            raw_text = ""
            if response and getattr(response, "content", None):
                raw_text = response.content[0].text  # type: ignore[attr-defined]
            raw_plan = _extract_json_object(raw_text)
        except Exception as exc:  # pragma: no cover - network
            logger.warning("Background planning via LLM failed: %s", exc)

    plan = _sanitize_mix_plan(raw_plan, duration_seconds, ambient_path, punctual_paths)
    if llm_attempted:
        ambient_summary, punctual_summary = _summarize_background_plan(plan)
        if plan["ambient"] or plan["punctual"]:
            logger.info(
                "LLM background plan for %s: ambient=%s | punctual=%s",
                voice_path.name,
                ambient_summary,
                punctual_summary,
            )
        else:
            logger.info(
                "LLM background plan for %s returned no usable cues; falling back to deterministic layout",
                voice_path.name,
            )

    if not plan["ambient"] and not plan["punctual"]:
        plan = _fallback_mix_plan(duration_seconds, ambient_path, punctual_paths)
        ambient_summary, punctual_summary = _summarize_background_plan(plan)
        logger.info(
            "Fallback background plan for %s: ambient=%s | punctual=%s",
            voice_path.name,
            ambient_summary,
            punctual_summary,
        )

    return plan


def apply_background_selection(
    voice_path: Path,
    project_name: str,
    scenario_text: Optional[str] = None,
) -> tuple[Path, int, Optional[Path], int, List[Dict[str, Any]]]:
    """
    Mix the user-selected background sounds under the generated narration.
    Si auto_backgrounds=True et aucun son manuellement sélectionné, déclenche
    la sélection intelligente à ce moment, en utilisant scenario_text pour le
    scoring narratif.

    Returns:
        (final_voice_path, layers_applied, dry_voice_path, requested_layers, plan_metadata)
    """
    try:
        selection = load_audio_selection(project_name)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Unable to load audio selection for %s: %s", project_name, exc)
        selection = {}

    background_selection = selection.get("backgrounds") or {}
    auto_bg = bool(selection.get("auto_backgrounds"))

    ambient_raw = background_selection.get("ambient") if isinstance(background_selection, dict) else None
    punctual_raws = background_selection.get("punctual") if isinstance(background_selection, dict) else background_selection
    punctual_raws = punctual_raws or []

    # Sélection automatique différée : s'exécute ici avec le texte du scénario
    if auto_bg and not ambient_raw and not punctual_raws:
        logger.info(
            "Auto-background selection triggered at generation time for project '%s' "
            "(scenario_text available: %s)",
            project_name,
            bool(scenario_text),
        )
        try:
            ambient_raw, punctual_raws = smart_select_backgrounds(
                project_name=project_name,
                scenario_text=scenario_text,
            )
        except Exception as exc:
            logger.warning("smart_select_backgrounds failed: %s", exc)
            ambient_raw = None
            punctual_raws = []

    def _resolve_background(raw_value: str) -> Optional[Path]:
        candidate = Path(raw_value)
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        else:
            candidate = candidate.resolve()
        return candidate if candidate.exists() else None

    ambient_selection: Optional[Dict[str, Any]] = None
    if isinstance(ambient_raw, str):
        resolved = _resolve_background(ambient_raw)
        if resolved:
            ambient_selection = {"raw": ambient_raw, "path": resolved}

    punctual_selections: List[Dict[str, Any]] = []
    for raw in punctual_raws:
        if not isinstance(raw, str):
            continue
        resolved = _resolve_background(raw)
        if resolved:
            punctual_selections.append({"raw": raw, "path": resolved})
        if len(punctual_selections) >= 2:
            break

    requested_layers = (1 if ambient_selection else 0) + len(punctual_selections)
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
    plan = build_background_mix_plan(
        scenario_text=scenario_text,
        voice_path=resolved_voice,
        duration_seconds=duration_seconds,
        ambient_path=ambient_selection["raw"] if ambient_selection else None,
        punctual_paths=[entry["raw"] for entry in punctual_selections],
    )
    if not plan["ambient"] and not plan["punctual"]:
        logger.info("No background plan generated for %s; leaving narration dry", project_name)
        return voice_path, 0, None, requested_layers, []

    mixed_segment = voice_segment
    plan_metadata: List[Dict[str, Any]] = []
    background_cache: Dict[str, AudioSegment] = {}

    def _get_segment(selection_entry: Dict[str, Any]) -> Optional[AudioSegment]:
        raw_value = selection_entry["raw"]
        cached = background_cache.get(raw_value)
        if cached is not None:
            return cached
        try:
            loaded = AudioSegment.from_file(selection_entry["path"])
        except Exception as exc:
            logger.warning("Failed to load background %s: %s", selection_entry["path"], exc)
            return None
        background_cache[raw_value] = loaded
        return loaded

    layers_applied = 0
    ambient_lookup = {ambient_selection["raw"]: ambient_selection} if ambient_selection else {}
    punctual_lookup = {entry["raw"]: entry for entry in punctual_selections}

    ambient_instruction = plan.get("ambient")
    if ambient_instruction:
        entry = ambient_lookup.get(ambient_instruction.get("file"))
        if entry:
            segment = _get_segment(entry)
            if segment:
                start_ms = max(0, int(float(ambient_instruction.get("start_seconds", 0.0)) * 1000))
                end_ms = max(start_ms + 1, int(float(ambient_instruction.get("end_seconds", 0.0)) * 1000))
                duration_ms = end_ms - start_ms
                if start_ms < len(mixed_segment) and duration_ms > 0:
                    available = len(mixed_segment) - start_ms
                    if available > 0:
                        duration_ms = min(duration_ms, available)
                        snippet = segment
                        if len(snippet) < duration_ms:
                            repeats = max(1, math.ceil(duration_ms / max(len(snippet), 1)))
                            snippet = snippet * repeats
                        snippet = snippet[:duration_ms]
                        try:
                            gain = float(ambient_instruction.get("gain_db", AMBIENT_GAIN_DB))
                        except (TypeError, ValueError):
                            gain = AMBIENT_GAIN_DB
                        snippet = snippet + gain
                        mixed_segment = mixed_segment.overlay(snippet, position=start_ms)
                        layers_applied += 1
                        plan_metadata.append(
                            {
                                "type": "ambient",
                                "background": entry["path"].name,
                                "start_seconds": round(start_ms / 1000, 2),
                                "duration_seconds": round(duration_ms / 1000, 2),
                                "note": ambient_instruction.get("note"),
                            }
                        )

    for instruction in plan.get("punctual", []):
        entry = punctual_lookup.get(instruction.get("file"))
        if not entry:
            continue
        segment = _get_segment(entry)
        if not segment:
            continue
        start_ms = max(0, int(float(instruction.get("start_seconds", 0.0)) * 1000))
        duration_ms = max(1, int(float(instruction.get("duration_seconds", PUNCTUAL_MIN_DURATION)) * 1000))
        if start_ms >= len(mixed_segment):
            continue
        available = len(mixed_segment) - start_ms
        if available <= 0:
            continue
        duration_ms = min(duration_ms, available)
        snippet = segment
        if len(snippet) < duration_ms:
            repeats = max(1, math.ceil(duration_ms / max(len(snippet), 1)))
            snippet = snippet * repeats
        snippet = snippet[:duration_ms]
        try:
            gain = float(instruction.get("gain_db", PUNCTUAL_GAIN_DB))
        except (TypeError, ValueError):
            gain = PUNCTUAL_GAIN_DB
        snippet = snippet + gain
        mixed_segment = mixed_segment.overlay(snippet, position=start_ms)
        layers_applied += 1
        plan_metadata.append(
            {
                "type": "punctual",
                "background": entry["path"].name,
                "start_seconds": round(start_ms / 1000, 2),
                "duration_seconds": round(duration_ms / 1000, 2),
                "note": instruction.get("note"),
            }
        )

    if layers_applied == 0:
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

    return final_path, layers_applied, dry_relative, requested_layers, plan_metadata


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


class ScenarioSpec(BaseModel):
    prompt: str = ""
    audience: Optional[str] = None
    tone: Optional[str] = None
    target_duration: Optional[int] = Field(default=None, ge=10, le=3600)
    source_usage_level: Optional[str] = Field(default=None, description="leger | modere | central")
    tts_provider: Optional[str] = Field(default=None, description="elevenlabs | qwen")
    tts_voice_id: Optional[str] = None


class ScenarioGenerationRequest(BaseModel):
    session_id: str
    prompt: str
    mode: str = "simple"
    output_dir: str = "./output"
    scenario_target: Optional[int] = Field(default=None, ge=1, le=5)
    model_id: Optional[str] = Field(default=None, description="Model key (opus, sonnet, gemini) or full OpenRouter ID")
    scenario_specs: Optional[List[ScenarioSpec]] = Field(default=None, description="Per-scenario overrides (prompt, audience, tone, duration, source_usage_level, tts)")


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
    backgrounds: Any = Field(default_factory=list)
    auto_backgrounds: bool = Field(default=False)
    tts_voice_id: Optional[str] = Field(default=None, description="Selected ElevenLabs voice identifier")


class TranscriptionUpdateRequest(BaseModel):
    file_name: str = Field(..., description="Audio file name within the project")
    transcription: str = Field(..., description="Edited transcript content")


class ScenarioAudioRequest(BaseModel):
    text: Optional[str] = None
    language: str = Field(default="French")


class ImageOrderPayload(BaseModel):
    order: List[str]


# ---------------------------------------------------------------------------
# Smart background selection — module-level (utilisé au moment de la génération)
# ---------------------------------------------------------------------------

_STOPWORDS_FR: set = {
    "de", "du", "des", "le", "la", "les", "un", "une", "et", "en",
    "au", "aux", "il", "elle", "ils", "elles", "je", "tu", "nous",
    "vous", "ce", "qui", "que", "quoi", "dont", "par", "pour", "sur",
    "sous", "avec", "sans", "dans", "est", "sont", "être", "avoir",
    "se", "si", "ne", "pas", "plus", "ou", "on", "leur", "leurs",
    "mon", "ton", "son", "ma", "ta", "sa", "mes", "tes", "ses",
    "nos", "vos", "ces", "cet", "cette", "tout", "tous", "toute",
    "toutes", "autre", "autres", "bien", "entre", "après", "avant",
    "alors", "car", "mais", "donc", "lors", "pendant", "selon",
    "vers", "depuis", "quand", "même", "très", "aussi", "comme",
    "the", "and", "of", "in", "a", "this", "that", "is", "are",
}


def _tokenize_text(text: str) -> set:
    """Tokenise un texte : minuscules, split sur non-alpha, filtre stopwords."""
    tokens = re.split(r"[^a-z\u00e0-\u00ff0-9]+", text.lower())
    return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS_FR}


def _extract_strings_recursive(obj: Any) -> str:
    """Extrait récursivement les chaînes d'un dict/list imbriqué."""
    if isinstance(obj, str):
        return obj if len(obj) >= 15 else ""
    if isinstance(obj, dict):
        return " ".join(_extract_strings_recursive(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(_extract_strings_recursive(item) for item in obj)
    return ""


def _build_narrative_keywords(project_name: str, scenario_text: Optional[str] = None) -> set:
    """
    Extrait les mots-clés du contexte narratif du projet.
    Si scenario_text est fourni (au moment de la génération), il est prioritaire.
    Sinon, utilise final_scenario / last_scenarios / project_notes du profil.
    """
    raw_texts: List[str] = []

    # Texte du scénario courant (disponible au moment de la génération)
    if scenario_text and scenario_text.strip():
        raw_texts.append(scenario_text)

    try:
        projects_dir = os.environ.get("PROJECTS_DIR")
        profile: Dict[str, Any] = load_project_config(
            project_name,
            projects_dir=projects_dir if projects_dir else None,
        )
    except Exception:
        profile = {}

    notes = profile.get("project_notes") or ""
    if notes.strip():
        raw_texts.append(notes)

    for scenario in (profile.get("last_scenarios") or []):
        raw_texts.append(_extract_strings_recursive(scenario))

    final = profile.get("final_scenario")
    if final:
        raw_texts.append(_extract_strings_recursive(final))

    if not raw_texts:
        return set()

    keywords = _tokenize_text(" ".join(raw_texts))
    logger.debug(
        "Narrative keywords for '%s' (%d tokens, scenario_text=%s): %s",
        project_name,
        len(keywords),
        bool(scenario_text),
        list(keywords)[:20],
    )
    return keywords


def _load_background_index(background_root: Optional[Path] = None) -> Dict[str, Any]:
    """Charge index.json et retourne un dict {filename -> entry}."""
    if background_root is None:
        background_root = (Path.cwd() / "data" / "audio" / "background_sounds").resolve()
    index_path = background_root / "index.json"
    if not index_path.exists():
        return {}
    try:
        with open(index_path, encoding="utf-8") as _f:
            _idx = json.load(_f)
        return {
            (e.get("filename") or "").strip(): e
            for e in _idx.get("sounds", [])
            if (e.get("filename") or "").strip()
        }
    except Exception as exc:
        logger.warning("Impossible de lire l'index des sons : %s", exc)
        return {}


def _narrative_relevance_score(entry: Dict[str, Any], keywords: set) -> float:
    """Score de pertinence narrative (0.0–1.0)."""
    if not keywords:
        return 0.5
    sound_tags: set = set()
    for tag in (entry.get("tags") or []):
        sound_tags |= _tokenize_text(tag)
    tags_matched = len(keywords & sound_tags)
    tags_score = tags_matched / max(len(sound_tags), 1)
    desc = (entry.get("metadata") or {}).get("description") or ""
    desc_words = _tokenize_text(desc)
    desc_matched = len(keywords & desc_words)
    desc_score = min(desc_matched / 5, 1.0)
    return tags_score * 0.70 + desc_score * 0.30


def _score_ambient_sound(entry: Dict[str, Any], narrative_keywords: set) -> float:
    """Score d'aptitude comme fond continu (0.0–1.0)."""
    tech = 0.0
    if entry.get("loop_friendly"):
        tech += 0.40
    intensity = (entry.get("metadata") or {}).get("intensity", "")
    if intensity == "low":
        tech += 0.30
    elif intensity == "medium":
        tech += 0.15
    duration = entry.get("duration") or 0.0
    if duration >= 120:
        tech += 0.30
    elif duration >= 60:
        tech += 0.20
    elif duration >= 30:
        tech += 0.08
    narr = _narrative_relevance_score(entry, narrative_keywords)
    return tech * 0.75 + narr * 0.25


def _score_punctual_sound(
    entry: Dict[str, Any],
    ambient_entry: Optional[Dict[str, Any]],
    narrative_keywords: set,
) -> float:
    """Score d'aptitude comme son ponctuel (0.0–1.0)."""
    tech = 0.0
    intensity = (entry.get("metadata") or {}).get("intensity", "")
    if intensity == "high":
        tech += 0.40
    elif intensity == "medium":
        tech += 0.25
    if ambient_entry:
        if entry.get("category") != ambient_entry.get("category"):
            tech += 0.30
        amb_act = (ambient_entry.get("metadata") or {}).get("activity", "")
        ent_act = (entry.get("metadata") or {}).get("activity", "")
        if amb_act and ent_act and ent_act != amb_act:
            tech += 0.30
    narr = _narrative_relevance_score(entry, narrative_keywords)
    return tech * 0.70 + narr * 0.30


def smart_select_backgrounds(
    project_name: str,
    scenario_text: Optional[str] = None,
    background_root: Optional[Path] = None,
) -> tuple[Optional[str], List[str]]:
    """
    Sélection intelligente des sons d'ambiance au moment de la génération audio.
    Scoring = métadonnées techniques + pertinence narrative (texte du scénario).

    Returns: (ambient_path, [punctual_path_1, punctual_path_2])
    """
    try:
        listing = find_background_sounds(limit=50)
    except Exception as exc:
        logger.warning("Smart background lookup failed: %s", exc)
        return None, []

    raw_files = listing.get("files") or []
    sound_index = _load_background_index(background_root)
    narrative_keywords = _build_narrative_keywords(project_name, scenario_text)

    logger.info(
        "Auto-select backgrounds for project '%s': %d sounds, %d narrative keywords, scenario_text=%s",
        project_name,
        len(raw_files),
        len(narrative_keywords),
        bool(scenario_text),
    )

    candidates: List[tuple[str, Dict[str, Any]]] = []
    for candidate in raw_files:
        path_str = candidate if isinstance(candidate, str) else (candidate.get("path") or "")
        if not path_str:
            continue
        fname = Path(path_str).name
        entry = sound_index.get(fname, {})
        candidates.append((path_str, entry))

    if not candidates:
        return None, []

    # Fond continu : meilleur score ambient
    scored_ambient = sorted(
        candidates,
        key=lambda x: _score_ambient_sound(x[1], narrative_keywords),
        reverse=True,
    )
    ambient_path, ambient_entry = scored_ambient[0]

    # Sons ponctuels parmi les restants
    remaining = [(p, e) for p, e in candidates if p != ambient_path]
    scored_punctual = sorted(
        remaining,
        key=lambda x: _score_punctual_sound(x[1], ambient_entry, narrative_keywords),
        reverse=True,
    )

    punctual: List[str] = []
    chosen_categories: set = set()
    for p_path, p_entry in scored_punctual:
        cat = p_entry.get("category", "")
        if cat and cat in chosen_categories:
            continue
        punctual.append(p_path)
        chosen_categories.add(cat)
        if len(punctual) >= 2:
            break

    if len(punctual) < 2:
        for p_path, _ in scored_punctual:
            if p_path not in punctual:
                punctual.append(p_path)
            if len(punctual) >= 2:
                break

    logger.info(
        "Smart background selection result: ambient=%s punctual=%s",
        ambient_path,
        punctual,
    )
    return ambient_path, punctual


def _truncate_preview_text(value: Optional[Any], max_chars: int = 400) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}…"


def _count_project_output_files(project_dir: Path) -> int:
    outputs_dir = project_dir / "outputs"
    if not outputs_dir.is_dir():
        return 0
    return sum(1 for p in outputs_dir.iterdir() if p.is_file() and not p.name.startswith("."))


def _tags_from_scenario_profile(profile: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    scenario_config = profile.get("scenario_config") or {}
    hist = scenario_config.get("historical_context") or {}
    themes = hist.get("themes") or {}
    for bucket in ("primary", "secondary"):
        raw = themes.get(bucket)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    t = item.strip()
                    if t and t not in tags:
                        tags.append(t)
        elif isinstance(raw, str):
            t = raw.strip()
            if t and t not in tags:
                tags.append(t)
    return tags[:8]


def _location_from_scenario_profile(profile: Dict[str, Any]) -> Optional[str]:
    scenario_config = profile.get("scenario_config") or {}
    hist = scenario_config.get("historical_context") or {}
    loc = hist.get("location") or {}
    primary = loc.get("primary")
    if isinstance(primary, str) and primary.strip():
        return primary.strip()
    return None


def _workflow_status_for_card(profile: Dict[str, Any]) -> str:
    if profile.get("finalized_at"):
        return "termine"
    last = profile.get("last_scenarios")
    if profile.get("final_scenario") or (isinstance(last, list) and len(last) > 0):
        return "en_cours"
    return "brouillon"


# ---------------------------------------------------------------------------


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

    def clean_elevenlabs_text(text: str) -> str:
        """Clean text for ElevenLabs v3 TTS:
        - [EXTRAIT AUDIO — Nom : "texte réel"] → keep only the quoted text after ':'
        - [ARCHIVE AUDIO — ...] / [ARCHIVE — ...] without quoted content → remove entirely
        - Ambient sound markers {filename.wav} → remove (handled by sound pipeline)
        - Part markers === PARTIE N : ... === → remove
        - All other [...] tags → KEEP (ElevenLabs v3 Audio Tags, interpreted natively)
        """
        # 1. Audio extract markers with quoted content after ':' → keep only the quoted text
        #    Handles: [EXTRAIT AUDIO — Gilles : "blah blah"] or [ARCHIVE — Nom : « blah »]
        def replace_audio_extract(m: re.Match) -> str:
            bracket_content = m.group(1)
            # Find content after ':'
            colon_idx = bracket_content.find(":")
            if colon_idx == -1:
                return ""
            after_colon = bracket_content[colon_idx + 1:].strip()
            # Extract content between quotes (French « » or standard " ")
            quote_match = re.search(r'[«""](.+?)[»""]', after_colon, re.DOTALL)
            if quote_match:
                return quote_match.group(1).strip()
            # No quotes: return everything after the colon if it looks like real text
            after_colon_clean = after_colon.strip().strip('""«»')
            if len(after_colon_clean) > 5:
                return after_colon_clean
            return ""

        # Apply to any [bracket content with a colon mentioning AUDIO/EXTRAIT/ARCHIVE]
        text = re.sub(
            r"\[((?:EXTRAIT|ARCHIVE)(?:\s+AUDIO)?\s*—[^\]]+)\]",
            replace_audio_extract,
            text,
            flags=re.IGNORECASE,
        )

        # 2. Remove ambient sound markers {filename.wav}
        text = re.sub(r"\{[^}]+\}", "", text)

        # 3. Remove part markers === PARTIE N : ... ===
        text = re.sub(r"===\s*PARTIE\s+\d+\s*:.*?===", "", text, flags=re.IGNORECASE)

        # 4. NOTE: remaining [...] tags are kept — ElevenLabs v3 Audio Tags
        #    e.g. [pause], [rit], [soupire], [chuchote], [triste], [en colère]…
        #    are interpreted natively by eleven_v3 and NOT read aloud.

        # 5. Clean up multiple newlines and extra spaces
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" +", " ", text)
        return text.strip()

    def scenario_to_text_for_elevenlabs(entry: Dict[str, Any]) -> str:
        """Extract text for ElevenLabs TTS, using taggedOutput if available."""
        # Check if taggedOutput exists at the entry level (from Agent 3)
        tagged_output = entry.get("taggedOutput")
        if isinstance(tagged_output, dict):
            tagged_text = tagged_output.get("taggedText")
            if isinstance(tagged_text, str) and tagged_text.strip():
                # Clean the tagged text: remove {} and [ARCHIVE ...] markers
                cleaned = clean_elevenlabs_text(tagged_text)
                if cleaned:
                    return cleaned
        
        # Also check inside scenario payload (in case structure is different)
        scenario_payload = extract_scenario_payload(entry)
        if scenario_payload:
            tagged_output = scenario_payload.get("taggedOutput")
            if isinstance(tagged_output, dict):
                tagged_text = tagged_output.get("taggedText")
                if isinstance(tagged_text, str) and tagged_text.strip():
                    cleaned = clean_elevenlabs_text(tagged_text)
                    if cleaned:
                        return cleaned
        
        # Fallback to regular scenario_to_text if no taggedOutput
        return scenario_to_text(entry)

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
        entry.setdefault("tts_provider", "elevenlabs")
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

        def _summarize_transcript(text: str) -> Dict[str, Any]:
            return summarize_transcript_robust(text)

        try:
            transcript = await loop.run_in_executor(None, _run_transcription)
            summary_payload: Optional[Dict[str, Any]] = None
            if transcript and transcript.strip():
                try:
                    summary_payload = await loop.run_in_executor(None, _summarize_transcript, transcript)
                except Exception as exc:  # pragma: no cover - external API failures are non-critical
                    logger.warning("Transcript summary failed for %s: %s", audio_path.name, exc)
            result_payload: Dict[str, Any] = {"transcription": transcript}
            if summary_payload:
                result_payload["summary"] = summary_payload
            save_analysis_result(
                analysis_type="transcription",
                source_path=str(audio_path),
                result=result_payload,
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
            try:
                await loop.run_in_executor(None, _rebuild_knowledge_graph, project_name)
            except Exception as exc:  # pragma: no cover - event extraction is best-effort
                logger.warning("Knowledge graph build failed for %s: %s", project_name, exc)
        except Exception as exc:
            log_progress(
                "TRANSCRIPTION_FAILED",
                project=project_name,
                file=audio_path.name,
                error=str(exc),
            )
            raise

    def _rebuild_knowledge_graph(project_name: str) -> None:
        from memoiredesterritoires.transcription.transcription_event_extraction import extract_events_robust

        data = fetch_analysis_results(
            analysis_type="transcription",
            source_path_contains=project_name,
            limit=50,
        )
        texts = [
            entry["result"]["transcription"]
            for entry in data.get("entries", [])
            if isinstance(entry.get("result"), dict) and entry["result"].get("transcription")
        ]
        combined = "\n\n".join(texts)
        if not combined.strip():
            return
        events_data = extract_events_robust(combined)
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        for idx, event in enumerate(events_data.get("events", [])):
            eid = f"event_{idx}"
            nodes[eid] = {
                "id": eid,
                "name": event.get("title", eid),
                "type": "Event",
                "description": event.get("description", ""),
                "time": event.get("approximate_time", ""),
            }
            for actor in event.get("actors", []) or []:
                if actor not in nodes:
                    nodes[actor] = {"id": actor, "name": actor, "type": "Person"}
                edges.append({"id": f"actor_{idx}_{actor}", "source": actor, "target": eid, "type": "PARTICIPATED_IN"})
            for place in event.get("places", []) or []:
                if place not in nodes:
                    nodes[place] = {"id": place, "name": place, "type": "Place"}
                edges.append({"id": f"place_{idx}_{place}", "source": eid, "target": place, "type": "HAPPENED_IN"})
            for kw in event.get("keywords", []) or []:
                if kw not in nodes:
                    nodes[kw] = {"id": kw, "name": kw, "type": "Keyword"}
                edges.append({"id": f"kw_{idx}_{kw}", "source": eid, "target": kw, "type": "HAS_TOPIC"})
        graph_data = {"nodes": list(nodes.values()), "edges": edges}
        project_path = settings.projects_dir / project_name
        project_path.mkdir(parents=True, exist_ok=True)
        (project_path / "events.json").write_text(json.dumps(events_data, ensure_ascii=False, indent=2), encoding="utf-8")
        (project_path / "graph.json").write_text(json.dumps(graph_data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(
            "Knowledge graph saved | project=%s events=%d nodes=%d",
            project_name,
            len(events_data.get("events", [])),
            len(nodes),
        )

    def fetch_project_transcriptions(project_name: str) -> List[Dict[str, Any]]:
        """Retrieve stored transcriptions for a project from the Parquet dataset."""
        try:
            data = fetch_analysis_results(
                analysis_type="transcription",
                source_path_contains=project_name,
                limit=50,
            )
            transcriptions: List[Dict[str, Any]] = []
            seen_titles: set[str] = set()
            for entry in data.get("entries", []):
                result = entry.get("result", {})
                text = result.get("transcription") if isinstance(result, dict) else None
                summary = result.get("summary") if isinstance(result, dict) else None
                title = entry.get("title") or Path(entry.get("source_path", "")).name
                if not text or not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                payload: Dict[str, Any] = {
                    "file_name": title,
                    "transcription": text,
                    "language": "fr",
                    "source": entry.get("source_path"),
                }
                if summary:
                    payload["summary"] = summary
                transcriptions.append(payload)
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
        provider = job["provider"] or "elevenlabs"
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

    async def _prefetch_voice_previews_task() -> None:
        async def _run() -> None:
            for voice_id in ELEVENLABS_DEFAULT_VOICE_IDS:
                try:
                    await _ensure_voice_preview_file(settings, voice_id)
                except Exception as exc:  # pragma: no cover - best-effort warmup
                    logger.warning("Voice preview warmup failed for %s: %s", voice_id, exc)
        asyncio.create_task(_run())

    app.router.on_startup.append(_start_tts_worker)
    app.router.on_startup.append(_prefetch_voice_previews_task)
    app.router.on_shutdown.append(_stop_tts_worker)

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
            "tts_ready": _tts_model_ready(),
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
                        "description_preview": _truncate_preview_text(profile.get("project_notes")),
                        "created_at": profile.get("created_at"),
                        "artifact_count": _count_project_output_files(child),
                        "tags": _tags_from_scenario_profile(profile),
                        "location": _location_from_scenario_profile(profile),
                        "workflow_status": _workflow_status_for_card(profile),
                        "has_k_graph": bool(profile.get("has_k_graph") or profile.get("k_graph_enabled")),
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
            "tts_provider": profile.get("tts_provider", "elevenlabs"),
            "tts_voice_id": profile.get("tts_voice_id"),
            "include_citations": profile.get("include_citations", True),
            "source_usage_level": profile.get("source_usage_level", "modere"),
            "preference_options": preference_options,
            "last_scenarios": profile.get("last_scenarios") or [],
            "last_scenarios_generated_at": profile.get("last_scenarios_generated_at"),
            "final_scenario": profile.get("final_scenario"),
            "final_audio": profile.get("final_audio"),
            "final_slideshow": profile.get("final_slideshow"),
            "audio_selection": audio_selection,
        }

    @app.delete("/projects/{project_name}", tags=["projects"])
    async def delete_project(project_name: str) -> dict:
        project_dir = settings.projects_dir / project_name
        if not project_dir.exists():
            raise HTTPException(status_code=404, detail="Projet introuvable")

        try:
            shutil.rmtree(project_dir)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Impossible de supprimer le projet: {exc}") from exc

        # Nettoyage des métadonnées de fichiers projet côté session store (best effort).
        try:
            project_meta_path = settings.session_store / f"{project_name}_files.json"
            if project_meta_path.exists():
                project_meta_path.unlink()
        except Exception as exc:
            logger.warning("Could not delete project files metadata for %s: %s", project_name, exc)

        # Nettoyage des sessions liées au projet supprimé (best effort).
        try:
            for session_file in settings.session_store.glob("*.json"):
                try:
                    payload = json.loads(session_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if payload.get("project_name") == project_name:
                    session_file.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Could not cleanup sessions for %s: %s", project_name, exc)

        log_progress("PROJECT_DELETED", project=project_name)
        return {"status": "deleted", "project": project_name}

    @app.get("/projects/{project_name}/transcriptions", tags=["projects"])
    async def get_project_transcriptions(project_name: str) -> dict:
        project_dir = settings.projects_dir / project_name
        if not project_dir.exists():
            raise HTTPException(status_code=404, detail="Projet introuvable")
        entries = fetch_project_transcriptions(project_name)
        return {"project": project_name, "transcriptions": entries}

    @app.post("/projects/{project_name}/transcriptions", tags=["projects"])
    async def update_project_transcription(project_name: str, payload: TranscriptionUpdateRequest) -> dict:
        if not payload.file_name.strip():
            raise HTTPException(status_code=400, detail="Nom de fichier manquant")
        audio_path = get_project_audio_file(project_name, payload.file_name)
        if not audio_path.exists():
            raise HTTPException(status_code=404, detail="Fichier audio introuvable")
        loop = asyncio.get_running_loop()
        summary_payload: Optional[Dict[str, Any]] = None
        text = payload.transcription or ""
        if text.strip():
            try:
                summary_payload = await loop.run_in_executor(None, summarize_transcript_robust, text)
            except Exception as exc:  # pragma: no cover - best effort summarization
                logger.warning("Manual transcription summary failed for %s/%s: %s", project_name, payload.file_name, exc)
        result_payload: Dict[str, Any] = {"transcription": text}
        if summary_payload:
            result_payload["summary"] = summary_payload
        save_analysis_result(
            analysis_type="transcription",
            source_path=str(audio_path),
            result=result_payload,
            title=payload.file_name,
            metadata={"project": project_name, "manual_edit": True},
            is_partial=False,
        )
        log_progress(
            "TRANSCRIPTION_UPDATED",
            project=project_name,
            file=payload.file_name,
        )
        return {"file_name": payload.file_name, "transcription": text, "summary": summary_payload}

    @app.get("/projects/{project_name}/transcriptions/{file_name}/download", tags=["projects"])
    async def download_project_transcription(project_name: str, file_name: str) -> PlainTextResponse:
        project_dir = settings.projects_dir / project_name
        if not project_dir.exists():
            raise HTTPException(status_code=404, detail="Projet introuvable")
        entries = fetch_project_transcriptions(project_name)
        entry = next((item for item in entries if item.get("file_name") == file_name), None)
        if not entry:
            raise HTTPException(status_code=404, detail="Transcription introuvable")
        text = entry.get("transcription", "")
        response = PlainTextResponse(content=text or "")
        response.headers["Content-Disposition"] = f'attachment; filename="{file_name}.txt"'
        return response

    @app.get("/projects/{project_name}/knowledge-graph", tags=["projects"])
    async def get_project_knowledge_graph(project_name: str) -> dict:
        project_path = settings.projects_dir / project_name
        events_file = project_path / "events.json"
        graph_file = project_path / "graph.json"
        events = json.loads(events_file.read_text(encoding="utf-8")) if events_file.exists() else {"events": []}
        graph = json.loads(graph_file.read_text(encoding="utf-8")) if graph_file.exists() else {"nodes": [], "edges": []}
        return {"project": project_name, "events": events.get("events", []), "graph": graph}

    @app.get("/projects/{project_name}/knowledge-graph-view", tags=["projects"])
    async def get_project_knowledge_graph_view(project_name: str):
        from fastapi.responses import HTMLResponse
        graph_file = settings.projects_dir / project_name / "graph.json"
        graph_data = json.loads(graph_file.read_text(encoding="utf-8")) if graph_file.exists() else {"nodes": [], "edges": []}
        graph_html_path = Path("graph.html")
        if not graph_html_path.exists():
            raise HTTPException(status_code=500, detail="graph.html template introuvable")
        template = graph_html_path.read_text(encoding="utf-8")
        html = template.replace("__GRAPH_DATA__", json.dumps(graph_data))
        return HTMLResponse(html)

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
        raw_backgrounds = selection.get("backgrounds") or []
        if isinstance(raw_backgrounds, dict):
            backgrounds = []
            ambient_value = raw_backgrounds.get("ambient")
            if isinstance(ambient_value, str) and ambient_value.strip():
                backgrounds.append(ambient_value.strip())
            punctual_values = raw_backgrounds.get("punctual") or []
            if isinstance(punctual_values, list):
                for candidate in punctual_values:
                    if isinstance(candidate, str) and candidate.strip():
                        backgrounds.append(candidate.strip())
        else:
            backgrounds = [bg for bg in raw_backgrounds if isinstance(bg, str) and bg.strip()]
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
            "tts_provider": project_profile.get("tts_provider", "elevenlabs"),
            "include_citations": project_profile.get("include_citations", True),
            "source_usage_level": project_profile.get("source_usage_level", "modere"),
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

            specs = req.scenario_specs or []
            if specs:
                aggregated_scenarios: List[dict] = []
                aggregated_config: Optional[dict] = None
                base_output_dir = Path(req.output_dir or "./output")
                for spec_idx, spec in enumerate(specs, start=1):
                    mark(2, "running", f"Scénario {spec_idx}/{len(specs)} : génération en cours")
                    spec_profile = dict(project_profile)
                    if spec.audience:
                        spec_profile["audience"] = spec.audience
                    if spec.tone:
                        spec_profile["tone"] = spec.tone
                    if spec.target_duration is not None:
                        spec_profile["target_duration"] = spec.target_duration
                    if spec.source_usage_level in {"leger", "modere", "central"}:
                        spec_profile["source_usage_level"] = spec.source_usage_level
                    spec_constraints = build_project_constraints(spec_profile)
                    spec_constraint_block = build_constraint_prompt_block(spec_constraints)
                    spec_overrides = build_config_overrides_from_constraints(spec_constraints)
                    user_prompt = (spec.prompt or "").strip()
                    chunks: List[str] = []
                    if project_notes and project_notes.strip():
                        chunks.append(project_notes.strip())
                    if spec_constraint_block:
                        chunks.append(spec_constraint_block)
                    if user_prompt:
                        chunks.append(user_prompt)
                    spec_prompt = "\n\n".join(chunks)
                    spec_params = dict(params)
                    spec_params["prompt"] = spec_prompt
                    spec_params["scenario_target"] = 1
                    spec_params["output_dir"] = str(
                        (base_output_dir / f"scenario_spec_{spec_idx}_{uuid4().hex[:4]}").resolve()
                    )
                    if spec.source_usage_level in {"leger", "modere", "central"}:
                        spec_params["source_usage_level"] = spec.source_usage_level
                    if spec.tts_provider in {"elevenlabs", "qwen"}:
                        spec_params["tts_provider"] = spec.tts_provider
                    if spec_overrides:
                        spec_params["config_overrides"] = spec_overrides
                    spec_result = await loop.run_in_executor(None, lambda p=spec_params: scenario_skill.run(p))
                    aggregated_config = aggregated_config or spec_result.get("config")
                    spec_scenarios = spec_result.get("scenarios", [])
                    if spec_scenarios and isinstance(spec_scenarios[0], dict):
                        scenario_payload = dict(spec_scenarios[0])
                        scenario_payload["scenario_index"] = spec_idx
                        scenario_payload["spec"] = {
                            "audience": spec.audience,
                            "tone": spec.tone,
                            "target_duration": spec.target_duration,
                            "source_usage_level": spec.source_usage_level,
                            "tts_provider": spec.tts_provider,
                            "tts_voice_id": spec.tts_voice_id,
                        }
                        aggregated_scenarios.append(scenario_payload)
                result = {"scenarios": aggregated_scenarios, "config": aggregated_config, "skill_metadata": {"scenario_count": len(aggregated_scenarios)}}
            else:
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
        
        profile = load_project_profile(session["project_name"])
        provider = (profile.get("tts_provider") or "elevenlabs").lower()
        voice_id = profile.get("tts_voice_id")
        
        # Check TTS model readiness only for Qwen (ElevenLabs uses API, no local model needed)
        if provider != "elevenlabs":
            tts_ready = _tts_model_ready()
            logger.info(
                "[TTS] Model readiness check - provider=%s, ready=%s, ready_file=%s",
                provider,
                tts_ready,
                _TTS_READY_FILE,
            )
            if not tts_ready:
                logger.warning(
                    "[TTS] Model not ready - provider=%s, ready_file missing at %s",
                    provider,
                    _TTS_READY_FILE,
                )
                raise HTTPException(
                    status_code=503,
                    detail="Le modèle TTS est en cours de téléchargement, réessayez dans quelques minutes.",
                )
        else:
            logger.info("[ElevenLabs] Skipping local TTS model check (using API)")
        
        logger.info(
            "[ElevenLabs] Starting audio synthesis - session=%s, provider=%s, voice_id=%s",
            session_id,
            provider,
            voice_id if voice_id else "NOT SET",
        )
        
        # Use tagged text for ElevenLabs, regular text for Qwen
        if provider == "elevenlabs":
            logger.info("[ElevenLabs] Extracting tagged text from scenario")
            text = (payload.text or scenario_to_text_for_elevenlabs(scenario)).strip()
            logger.info(
                "[ElevenLabs] Tagged text extracted - length=%d chars, preview=%s",
                len(text),
                text[:200] + "..." if len(text) > 200 else text,
            )
        else:
            text = (payload.text or scenario_to_text(scenario)).strip()
        
        if not text:
            logger.error("[ElevenLabs] Empty text extracted - cannot generate audio")
            raise HTTPException(status_code=400, detail="Impossible de générer l'audio : texte vide")
        log_progress(
            "SCENARIO_AUDIO_START",
            session=session_id,
            project=session["project_name"],
            language=payload.language or "French",
        )

        def synthesize_qwen() -> dict:
            return text_to_speech_with_instructions(
                text=text,
                project_name=session["project_name"],
                language=payload.language or "French",
            )

        if provider == "elevenlabs":
            if not voice_id:
                logger.error("[ElevenLabs] No voice_id configured in project profile")
                raise HTTPException(
                    status_code=400,
                    detail="Sélectionnez une voix ElevenLabs avant de générer l'audio."
                )
            logger.info(
                "[ElevenLabs] Calling eleven_labs_tts - voice_id=%s, text_length=%d chars",
                voice_id,
                len(text),
            )
            try:
                result = eleven_labs_tts(
                    text=text,
                    voice_id=voice_id,
                )
                logger.info(
                    "[ElevenLabs] Synthesis successful - output_path=%s, status=%s",
                    result.get("path", "unknown"),
                    result.get("status", "unknown"),
                )
            except Exception as exc:  # pragma: no cover - propagate
                logger.exception(
                    "[ElevenLabs] Synthesis failed - session=%s, voice_id=%s, text_length=%d, error=%s",
                    session_id,
                    voice_id,
                    len(text),
                    str(exc),
                )
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            result.setdefault("language", payload.language or "French")
            result.setdefault("sample_rate", 44100)
            try:
                segment = AudioSegment.from_file(result["path"])
                result["num_samples"] = int(segment.frame_count())
            except Exception:
                result.setdefault("num_samples", 0)
            result["tts_provider"] = "elevenlabs"
        else:
            try:
                result = synthesize_qwen()
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
                        result = synthesize_qwen()
                    except Exception as retry_exc:
                        raise HTTPException(status_code=400, detail=str(retry_exc)) from retry_exc
                else:
                    raise HTTPException(status_code=400, detail=message) from exc
            except Exception as exc:  # pragma: no cover - propagate to client
                logger.exception("Scenario audio synthesis failed for session %s", session_id)
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            result["tts_provider"] = "qwen"

        backgrounds_applied = 0
        backgrounds_requested = 0
        dry_voice_path: Optional[Path] = None
        background_plan: List[Dict[str, Any]] = []
        try:
            voice_path = Path(result["path"])
            (
                layered_path,
                backgrounds_applied,
                dry_voice_path,
                backgrounds_requested,
                background_plan,
            ) = apply_background_selection(voice_path, session["project_name"], text)
            result["path"] = str(layered_path)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Background layering failed for session %s: %s", session_id, exc)
            backgrounds_applied = 0
            background_plan = []

        metadata = {
            **result,
            "generated_at": datetime.utcnow().isoformat(),
            "text_length": len(text),
            "language": payload.language or "French",
            "backgrounds_applied": backgrounds_applied,
            "background_tracks_requested": backgrounds_requested,
        }
        if background_plan:
            metadata["background_plan"] = background_plan
        if dry_voice_path:
            metadata["voice_only_path"] = str(dry_voice_path)
        session_store.save_scenario_audio(session_id, metadata)

        if backgrounds_applied:
            log_progress(
                "SCENARIO_AUDIO_BACKGROUND_APPLIED",
                session=session_id,
                project=session["project_name"],
                layers=backgrounds_applied,
            )
        elif backgrounds_requested:
            log_progress(
                "SCENARIO_AUDIO_BACKGROUND_SKIPPED",
                session=session_id,
                project=session["project_name"],
                reason="mix_failed",
            )

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

    @app.get("/projects/{project_name}/audio-file", tags=["projects"])
    async def stream_project_audio_file(project_name: str, file: str = Query(..., description="File name under the project audio/ directory")):
        try:
            audio_path = get_project_audio_file(project_name, file)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(audio_path)

    @app.get("/projects/{project_name}/transcription-bundle", tags=["projects"])
    async def download_transcription_bundle(project_name: str):
        import io
        import zipfile

        project_path = settings.projects_dir / project_name
        if not project_path.exists():
            raise HTTPException(status_code=404, detail="Projet introuvable")

        transcripts = fetch_project_transcriptions(project_name)
        events_file = project_path / "events.json"
        graph_file = project_path / "graph.json"

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for entry in transcripts:
                file_name = entry.get("file_name") or "transcription.txt"
                safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(file_name).stem) or "transcription"
                zf.writestr(f"transcriptions/{safe_name}.txt", entry.get("transcription") or "")
                if entry.get("summary"):
                    zf.writestr(f"summaries/{safe_name}.json", json.dumps(entry["summary"], ensure_ascii=False, indent=2))
            if events_file.exists():
                zf.writestr("events.json", events_file.read_text(encoding="utf-8"))
            if graph_file.exists():
                zf.writestr("graph.json", graph_file.read_text(encoding="utf-8"))
        buffer.seek(0)

        from fastapi.responses import StreamingResponse

        safe_project = re.sub(r"[^A-Za-z0-9._-]+", "_", project_name) or "project"
        headers = {"Content-Disposition": f'attachment; filename="{safe_project}_transcriptions.zip"'}
        return StreamingResponse(buffer, media_type="application/zip", headers=headers)

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

    @app.get("/tts/preview", tags=["tts"])
    async def get_voice_preview(
        voice_id: str = Query(..., description="Identifiant ElevenLabs de la voix pour pré-écoute"),
    ):
        normalized = voice_id.strip()
        if not normalized:
            raise HTTPException(status_code=400, detail="La voix demandée est invalide.")
        try:
            preview_path = await _ensure_voice_preview_file(settings, normalized)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - external API
            logger.warning("ElevenLabs preview failed for %s: %s", normalized, exc)
            raise HTTPException(status_code=502, detail=f"Impossible de générer l'aperçu audio: {exc}") from exc

        return FileResponse(
            preview_path,
            media_type="audio/mpeg",
            filename=preview_path.name,
        )

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
        provider = profile.get("tts_provider", "elevenlabs")
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

        def _sanitize_background(path_value: Optional[str]) -> Optional[str]:
            if not path_value:
                return None
            try:
                resolved = resolve_background_path(path_value)
            except HTTPException:
                return None
            if not resolved.exists():
                return None
            return path_value

        ambient_choice: Optional[str] = None
        punctual_choices: List[str] = []
        raw_backgrounds = payload.backgrounds
        if isinstance(raw_backgrounds, dict):
            ambient_choice = _sanitize_background(raw_backgrounds.get("ambient"))
            punctual_source = raw_backgrounds.get("punctual") or []
        else:
            punctual_source = raw_backgrounds if isinstance(raw_backgrounds, list) else []
        for candidate in punctual_source:
            path_value = _sanitize_background(candidate)
            if path_value and path_value not in punctual_choices:
                punctual_choices.append(path_value)
            if len(punctual_choices) >= 2:
                break

        # Si auto_backgrounds, on ne pré-sélectionne rien : la sélection se fera
        # au moment de la génération audio (apply_background_selection), avec le
        # texte du scénario disponible pour le scoring narratif.
        if payload.auto_backgrounds:
            ambient_choice = None
            punctual_choices = []

        selection_payload: Dict[str, Any] = {
            "voices": voices,
            "backgrounds": {
                "ambient": ambient_choice,
                "punctual": punctual_choices,
            },
            "auto_backgrounds": payload.auto_backgrounds,
        }
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
        total_backgrounds = (1 if ambient_choice else 0) + len(punctual_choices)
        log_progress(
            "AUDIO_SELECTION_UPDATED",
            session=session_id,
            project=payload.project_name,
            voices=len(voices),
            backgrounds=total_backgrounds,
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

        # Charger l'index de métadonnées (tags, description, catégorie…)
        sound_index: Dict[str, Any] = {}
        index_path = background_root / "index.json"
        if index_path.exists():
            try:
                with open(index_path, encoding="utf-8") as _f:
                    _idx = json.load(_f)
                for _entry in _idx.get("sounds", []):
                    _fname = (_entry.get("filename") or "").strip()
                    if _fname:
                        sound_index[_fname] = _entry
            except Exception as _exc:
                logger.warning("Impossible de lire l'index des sons : %s", _exc)

        files = []
        for rel in listing.get("files", []):
            fname = Path(rel).name
            meta = sound_index.get(fname, {})
            files.append(
                {
                    "path": rel,
                    "name": fname,
                    "preview": f"/background-sounds/preview?path={quote(rel)}",
                    "category": meta.get("category") or Path(rel).parent.name,
                    "tags": meta.get("tags") or [],
                    "description": (meta.get("metadata") or {}).get("description") or "",
                    "duration": meta.get("duration"),
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
                frontend_notes = payload.get("project_notes") or None
                await chat_agent.handle_message(session_id, text, session_store, websocket, frontend_notes=frontend_notes)
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
