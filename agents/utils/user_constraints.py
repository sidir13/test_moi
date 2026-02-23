"""
Helpers to expose user-provided constraints from the “Détails du projet” step.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

DETAIL_LABELS: Dict[str, str] = {
    "public_cible": "Public cible",
    "ton": "Ton narratif",
    "duree": "Durée audio ciblée",
}


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, (int, float)):
        text = f"{value}"
        return text[:-2] if text.endswith(".0") else text
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        rendered = ", ".join(str(item) for item in value if item not in (None, ""))
        return rendered.strip()
    if isinstance(value, dict):
        if {"start_year", "end_year"} <= value.keys():
            return f"{value['start_year']}–{value['end_year']}"
        if "value" in value:
            return _format_value(value["value"])
    return str(value)


def _collect_user_briefs(config: Dict[str, Any]) -> List[str]:
    scenario_config = config.get("scenario_config") or {}
    user_input = scenario_config.get("user_input") or {}
    briefs: List[str] = []

    original_prompt = (user_input.get("original_prompt") or "").strip()
    if original_prompt:
        briefs.append(original_prompt)

    project_notes = (
        config.get("project_notes")
        or scenario_config.get("project_notes")
        or config.get("project_brief")
    )
    if isinstance(project_notes, str) and project_notes.strip():
        briefs.append(project_notes.strip())
    return briefs


def _get_detail_value(gen_params: Dict[str, Any], key: str) -> Optional[str]:
    entry = gen_params.get(key)
    if not isinstance(entry, dict):
        return None
    if not entry.get("user_specified"):
        return None
    value = _format_value(entry.get("value"))
    return value or None


def _resolve_duration(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return None
    return max(30, seconds)


def build_user_requirement_block(config: Dict[str, Any]) -> str:
    """
    Build a compact block with only the fields the user edited inside Détails du projet.
    """

    scenario_config = config.get("scenario_config") or {}
    gen_params = scenario_config.get("generation_parameters") or {}
    metadata = scenario_config.get("metadata") or {}
    project_constraints = metadata.get("project_constraints") or {}

    briefs = _collect_user_briefs(config)
    lines: List[str] = []
    if briefs:
        lines.append("=== BRIEF UTILISATEUR À RESPECTER MOT POUR MOT ===")
        lines.extend(briefs)

    audience = (
        config.get("audience")
        or _get_detail_value(gen_params, "public_cible")
        or project_constraints.get("audience")
    )
    tone = (
        config.get("tone")
        or _get_detail_value(gen_params, "ton")
        or project_constraints.get("tone")
    )
    duration_seconds = (
        _resolve_duration(config.get("target_duration"))
        or _resolve_duration(_get_detail_value(gen_params, "duree"))
        or _resolve_duration(project_constraints.get("duration_seconds"))
    )
    voice_hint = (
        config.get("voice_instructions")
        or scenario_config.get("voice_instructions")
        or project_constraints.get("voice_instructions")
    )

    preference_lines: List[str] = []
    if audience:
        preference_lines.append(f"- Public cible : {audience}")
    if tone:
        preference_lines.append(f"- Ton narratif : {tone}")
    if duration_seconds:
        mins = duration_seconds // 60
        secs = duration_seconds % 60
        human = []
        if mins:
            human.append(f"{mins} min")
        if secs or not human:
            human.append(f"{secs:02d} s" if mins else f"{secs} s")
        preference_lines.append(
            f"- Durée audio ciblée : ~{duration_seconds} s ({' '.join(human)})"
        )
    if voice_hint:
        preference_lines.append(f"- Consignes vocales : {voice_hint}")

    if preference_lines:
        lines.append('=== PARAMÈTRES SAISIS DANS "DÉTAILS DU PROJET" ===')
        lines.extend(preference_lines)

    if not lines:
        return ""
    lines.append(
        "Utilise ces indications pour guider ton écriture, sans les citer mot pour mot ni "
        "expliquer que tu suis des consignes. Le texte final ne doit jamais mentionner qu'il "
        "s'adresse à un certain public sur ordre ou qu'un ton a été imposé."
    )
    lines.append("Tout scénario ou structure qui s'éloigne de ces exigences doit être rejeté.")
    return "\n".join(lines)
