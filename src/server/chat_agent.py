"""Chat agent that proxies websocket messages to the Anthropic workflow."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
import logging

from anthropic import Anthropic, AuthenticationError
from dotenv import load_dotenv

load_dotenv()

try:
    from main import TOOLS, build_skill_context, check_available_skills, execute_tool
except ImportError:  # pragma: no cover - convenience for direct execution
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from main import TOOLS, build_skill_context, check_available_skills, execute_tool


def _normalize_base_url(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip().strip('"').strip("'")
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        value = "https://" + value.lstrip("/")
    return value

logger = logging.getLogger(__name__)


def _mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}…{value[-3:]}"


class ChatAgent:
    def __init__(self) -> None:
        self.skill_context = build_skill_context(check_available_skills())
        self.api_key = os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY")
        base_url_value = _normalize_base_url(os.getenv("ANTHROPIC_BASE_URL"))
        self.model = os.getenv("ANTHROPIC_CHAT_MODEL", "anthropic/claude-sonnet-4-20250514")
        self.client = None
        logger.info(
            "ChatAgent init — api key present: %s, base_url: %s, model: %s",
            "yes" if self.api_key else "no",
            base_url_value or "default",
            self.model,
        )
        logger.debug(
            "Env snapshot: ANTHROPIC_AUTH_TOKEN=%s ANTHROPIC_API_KEY=%s ANTHROPIC_BASE_URL=%s",
            _mask(os.getenv("ANTHROPIC_AUTH_TOKEN")),
            _mask(os.getenv("ANTHROPIC_API_KEY")),
            os.getenv("ANTHROPIC_BASE_URL"),
        )
        if self.api_key:
            client_kwargs = {"api_key": self.api_key}
            if base_url_value:
                client_kwargs["base_url"] = base_url_value
            self.client = Anthropic(**client_kwargs)
        if not self.client:
            logger.warning("ChatAgent initialized without Anthropic credentials")

    async def handle_message(self, session_id: str, user_text: str, session_store, websocket, *, frontend_notes: str | None = None, scenario_prompts: list | None = None, tagged_paragraphs: list | None = None, tts_provider: str | None = None) -> None:
        if not self.client:
            await websocket.send_json({"type": "error", "message": "Missing Anthropic credentials"})
            return
        user_text = (user_text or "").strip()
        if not user_text:
            await websocket.send_json({"type": "error", "message": "Message vide"})
            return

        history = session_store.get_chat_history(session_id)
        messages: List[Dict[str, Any]] = history[:] if history else []

        # Inject project context on first message so agent knows the project_name
        session_data = session_store.load_session(session_id) if hasattr(session_store, "load_session") else {}
        project_name = (session_data or {}).get("project_name", "") if isinstance(session_data, dict) else ""

        # Read current project_notes in real time so agent always sees latest textarea content
        # frontend_notes (sent from browser) takes priority over what's stored in config.json
        project_notes_context = ""
        if project_name:
            _notes = ""
            if frontend_notes and frontend_notes.strip():
                _notes = frontend_notes.strip()
            else:
                try:
                    from memoiredesterritoires.project_config import load_project_config
                    _cfg = load_project_config(project_name)
                    _notes = (_cfg or {}).get("project_notes", "")
                except Exception:
                    pass
            if _notes and _notes.strip():
                project_notes_context = f"\n\n[Contexte narratif actuel du projet (textarea) :\n{_notes.strip()}\n]"

        # Build scenario prompts context from live frontend values
        scenario_prompts_context = ""
        if scenario_prompts:
            lines = [f"  Scénario {i+1} : \"{p}\"" for i, p in enumerate(scenario_prompts)]
            scenario_prompts_context = "\n\n[Prompts actuels des scénarios du formulaire :\n" + "\n".join(lines) + "\n]"

        # Build tagged paragraphs context from live frontend values (edition_text page)
        tagged_paragraphs_context = ""
        if tagged_paragraphs:
            parts = []
            for p in tagged_paragraphs:
                parts.append(f"  Paragraphe {p.get('partie_id', '?')} — {p.get('titre', '')}:\n{p.get('taggedText', '')}")
            tagged_paragraphs_context = "\n\n[Paragraphes actuels du scénario en édition (texte balisé) :\n" + "\n\n".join(parts) + "\n]"

        # Inject TTS provider context so LLM knows which tags are allowed
        tts_context = ""
        if tts_provider:
            if tts_provider == "qwen":
                tts_context = "\n\n[Provider TTS actif : Qwen (local) — les balises {nom.wav} sont INTERDITES. Utiliser uniquement [pause Xs], [silence Xs] et instructions de voix.]"
            else:
                tts_context = "\n\n[Provider TTS actif : ElevenLabs — les balises {nom.wav} (effet sonore) sont autorisées.]"
        tagged_paragraphs_context += tts_context

        project_context = f"\n\n[Contexte session : projet actif = \"{project_name}\", session_id = {session_id}]{project_notes_context}{scenario_prompts_context}{tagged_paragraphs_context}" if project_name else (scenario_prompts_context + tagged_paragraphs_context)

        if project_name:
            payload = f"[projet: \"{project_name}\"] {user_text}{project_context}"
        else:
            payload = user_text + (project_context if project_context else "")
        messages.append({"role": "user", "content": payload})

        loop = asyncio.get_running_loop()

        while True:
            try:
                response = await loop.run_in_executor(
                    None,
                lambda: self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    tools=TOOLS,
                    system=(
                        "Tu es un assistant proactif et expert qui aide l'utilisateur à préparer son projet d'archive sonore historique.\n\n"

                        "══════ CONTEXTE NARRATIF — RÈGLE ABSOLUE ══════\n"
                        "Chaque message utilisateur contient un bloc [Contexte narratif actuel du projet (textarea) : ...] qui reflète EXACTEMENT ce que l'utilisateur a tapé dans le textarea, en temps réel — y compris les modifications non sauvegardées.\n"
                        "CE BLOC EST LA SOURCE DE VÉRITÉ UNIQUE. Lis-le à chaque message.\n"
                        "Quand l'utilisateur demande de 'corriger', 'reformuler', 'améliorer', 'raccourcir' ou 'modifier' le texte : travaille UNIQUEMENT sur le contenu de ce bloc, pas sur une version sauvegardée.\n"
                        "Appelle ensuite 'update_project_notes' avec la version corrigée/modifiée de CE texte.\n\n"

                        "══════ VOIX ELEVENLABS — RÈGLE ABSOLUE ══════\n"
                        "Il existe 9 voix ElevenLabs prédéfinies pour la SYNTHÈSE DE LA NARRATION. Ce ne sont PAS des fichiers audio — ce sont des IDs de voix dans le système.\n"
                        "Quand l'utilisateur dit 'sélectionne la voix X' ou 'choisis une voix d'enfant' → appelle IMMÉDIATEMENT 'select_voice' avec l'ID correspondant.\n"
                        "NE DEMANDE JAMAIS de fichier, de chemin ou de description. NE DIS PAS que tu n'as pas accès aux fichiers.\n"
                        "MAPPING (à utiliser directement) :\n"
                        "  Voix 1 → 5l4ttmr4SKNgi0HnOelT  (Paul K — homme français, voix grave et chaleureuse, narrateur documentaire)\n"
                        "  Voix 2 → flHkNRp1BlvT73UL6gyz  (Jessica — femme américaine, personnage expressif, ton dramatique)\n"
                        "  Voix 3 → jK7dAsiVAhbApIS8KkWB  (Vincent — homme, voix fluide et expressive, narration et pub)\n"
                        "  Voix 4 → NOpBlnGInO9m6vDvFkFC  (Grandpa Spuds — homme âgé américain, grand-père conteur)\n"
                        "  Voix 5 → jUHQdLfy668sllNiNTSW  (Clément — homme français parisien, narrateur calme et clair, audioguides)\n"
                        "  Voix 6 → tKaoyJLW05zqV0tIH9FD  (Gaëlle — femme française, voix chaleureuse pour audiobooks et contes)\n"
                        "  Voix 7 → T4BwQ2ZwlS2BbHIfci4H  (Souni — femme française jeune, voix douce pour narration)\n"
                        "  Voix 8 → GYzIdoKkRyANjBvkKYfO  (Koraly — femme française parisienne, voix captivante pour audioguides et musées)\n"
                        "  Voix 9 → TojRWZatQyy9dujEdiQ1  (Koraly Storyteller — femme française, voix immersive pour audiobooks)\n"
                        "Exemple : 'sélectionne la voix 1' → select_voice(voice_id='5l4ttmr4SKNgi0HnOelT', voice_label='Voix 1', project_name=<projet_actif>)\n"
                        "Exemple : 'voix d'enfant' → select_voice(voice_id='NOpBlnGInO9m6vDvFkFC', voice_label='Voix 4', ...)\n\n"

                        "══════ DISTINCTION CRITIQUE ══════\n"
                        "'auto_select_audio' = sélectionner des FICHIERS ENREGISTRÉS uploadés par l'utilisateur (interviews, témoignages à transcrire). À N'UTILISER QUE pour les fichiers du projet.\n"
                        "'select_voice' = choisir UNE des 9 voix ElevenLabs pour la synthèse vocale. À utiliser quand on parle de Voix 1-9.\n\n"

                        "AUTRES ACTIONS DIRECTES :\n"
                        "- Ambiances sonores → 'find_background_sounds' puis 'select_audio_manually'\n"
                        "- Fichiers audio enregistrés → 'auto_select_audio'\n"
                        "- Transcriptions existantes → 'list_analysis_results'\n"
                        "- Transcrire → 'transcribe_audio'\n"
                        "- Brief projet → 'update_project_notes'\n"
                        "- Prompt de scénario → 'update_prompt_field'\n\n"

                        "══════ CHAMP PROMPT SCÉNARIO — RÈGLE ABSOLUE ══════\n"
                        "Chaque message utilisateur peut contenir un bloc [Prompts actuels des scénarios du formulaire : ...] qui reflète le contenu actuel des champs 'prompt' sur la page de configuration des scénarios.\n"
                        "CE BLOC EST LA SOURCE DE VÉRITÉ pour les prompts. Lis-le avant toute modification.\n"
                        "Quand l'utilisateur demande de 'générer', 'améliorer', 'corriger', 'raccourcir' ou 'traduire' un prompt de scénario → appelle TOUJOURS 'update_prompt_field' avec le résultat. Ne mets JAMAIS le texte généré dans le chat — applique-le directement via l'outil.\n"
                        "Paramètre 'scenario_index' : 0 = premier scénario, 1 = deuxième, etc. (défaut : 0 si non précisé).\n\n"

                        "══════ ÉDITION DU TEXTE BALISÉ — RÈGLE ABSOLUE ══════\n"
                        "Sur la page d'édition (edition_text), chaque message contient un bloc [Paragraphes actuels du scénario en édition...] avec le texte exact de chaque paragraphe incluant ses balises.\n"
                        "CE BLOC EST LA SOURCE DE VÉRITÉ UNIQUE pour le texte en cours d'édition.\n"
                        "Quand l'utilisateur demande de : supprimer un paragraphe, modifier/corriger/ajouter du texte, ajouter ou supprimer des balises ({fichier.wav}, [pause Xs], [instruction]) → appelle TOUJOURS 'update_tagged_scenario' avec la liste COMPLÈTE et mise à jour de TOUS les paragraphes.\n"
                        "Règles balises : {nom.wav} = effet sonore (UNIQUEMENT si ElevenLabs — INTERDIT si Qwen), [pause Xs] ou [silence Xs] = respiration, [ton X] [murmure] etc. = instruction voix.\n"
                        "Suppression de paragraphe : renumérote les partie_id restants pour qu'ils soient consécutifs (1, 2, 3…).\n"
                        "PLACEMENT PRÉCIS DE BALISES — RÈGLE ABSOLUE :\n"
                        "Quand l'utilisateur dit 'ajoute une respiration après [mot/phrase]', 'place un effet sonore avant [X]', 'mets une pause ici' ou formulation équivalente :\n"
                        "1. Trouve le texte exact dans le paragraphe concerné (source de vérité = bloc [Paragraphes actuels...]).\n"
                        "2. Insère la balise AU BON ENDROIT dans la chaîne de caractères du paragraphe. Ex : 'bonjour [pause 2s] monde'.\n"
                        "3. Appelle immédiatement update_tagged_scenario avec le texte modifié.\n"
                        "Si l'utilisateur laisse le LLM décider où placer les balises : place-les aux endroits narrativement pertinents (fins de phrases, moments de tension, pauses naturelles).\n"
                        "Ne mets JAMAIS le texte modifié dans le chat — applique-le directement via l'outil.\n\n"

                        "RÈGLE : N'utilise JAMAIS 'generate_historical_scenario' sauf si l'utilisateur dit explicitement 'génère les scénarios'.\n"
                        "Sois proactif : agis immédiatement sans demander confirmation inutile."
                    ),
                    messages=messages,
                ),
            )
            except AuthenticationError as exc:
                logger.error("Anthropic authentication failed: %s", exc)
                await websocket.send_json({
                    "type": "error",
                    "message": "Anthropic authentication error — verify API key/base URL in .env",
                })
                return

            if response.stop_reason == "end_turn":
                serialized = _serialize_blocks(response.content)
                text_blocks = [block["text"] for block in serialized if block.get("type") == "text"]
                for chunk in text_blocks:
                    await websocket.send_json({"type": "assistant_text", "text": chunk})
                messages.append({"role": "assistant", "content": serialized})
                break

            if response.stop_reason == "tool_use":
                serialized = _serialize_blocks(response.content)
                messages.append({"role": "assistant", "content": serialized})
                tool_results_payload: List[Dict[str, Any]] = []
                for block in serialized:
                    if block.get("type") != "tool_use":
                        continue
                    await websocket.send_json({
                        "type": "tool_call",
                        "tool": block["name"],
                        "input": block.get("input", {}),
                    })
                    logger.info("Tool call %s input=%s", block["name"], block.get("input"))
                    result = await loop.run_in_executor(None, execute_tool, block["name"], block.get("input", {}))
                    await websocket.send_json({
                        "type": "tool_result",
                        "tool": block["name"],
                        "result": _safe_serialize(result),
                    })
                    tool_results_payload.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.get("id"),
                            "content": _safe_serialize(result),
                        }
                    )
                if not tool_results_payload:
                    break
                messages.append({"role": "user", "content": tool_results_payload})
                continue

            await websocket.send_json(
                {"type": "error", "message": f"Conversation stoppée: {response.stop_reason}"}
            )
            break

        session_store.save_chat_history(session_id, _json_safe(messages))
        await websocket.send_json({"type": "done"})


def _serialize_blocks(blocks: Any) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for block in blocks or []:
        if isinstance(block, dict):
            serialized.append(block)
            continue
        block_type = getattr(block, "type", None)
        entry: Dict[str, Any] = {"type": block_type}
        if block_type == "text":
            entry["text"] = getattr(block, "text", "")
        elif block_type == "tool_use":
            entry["id"] = getattr(block, "id", None)
            entry["name"] = getattr(block, "name", "")
            entry["input"] = getattr(block, "input", {})
        else:
            entry["content"] = getattr(block, "content", None)
        serialized.append(entry)
    return serialized


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=_safe_serialize))


def _safe_serialize(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


if __name__ == "__main__":
    import argparse

    class _MemoryStore:
        def __init__(self):
            self._history = {}

        def get_chat_history(self, session_id: str) -> list:
            return self._history.get(session_id, [])

        def save_chat_history(self, session_id: str, history: list) -> None:
            self._history[session_id] = history

    class _ConsoleWebSocket:
        async def send_json(self, payload: dict) -> None:
            print(payload)

    async def _run(prompt: str) -> None:
        agent = ChatAgent()
        store = _MemoryStore()
        ws = _ConsoleWebSocket()
        await agent.handle_message("cli-session", prompt, store, ws)

    parser = argparse.ArgumentParser(description="Test ChatAgent pipeline via CLI.")
    parser.add_argument("prompt", nargs="?", default="Peux-tu résumer la situation ?", help="Message à envoyer au chatbot")
    args = parser.parse_args()

    asyncio.run(_run(args.prompt))
