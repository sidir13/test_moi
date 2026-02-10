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

    async def handle_message(self, session_id: str, user_text: str, session_store, websocket) -> None:
        if not self.client:
            await websocket.send_json({"type": "error", "message": "Missing Anthropic credentials"})
            return
        user_text = (user_text or "").strip()
        if not user_text:
            await websocket.send_json({"type": "error", "message": "Message vide"})
            return

        history = session_store.get_chat_history(session_id)
        messages: List[Dict[str, Any]] = history[:] if history else []

        payload = f"{user_text}\n\n{self.skill_context}" if not messages else user_text
        messages.append({"role": "user", "content": payload})

        loop = asyncio.get_running_loop()

        while True:
            try:
                response = await loop.run_in_executor(
                    None,
                lambda: self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    tools=TOOLS,
                    system="Tu es un assistant qui aide l'utilisateur à préparer son projet d'archive sonore historique. IMPORTANT: N'utilise JAMAIS le tool 'generate_historical_scenario' sauf si l'utilisateur te demande EXPLICITEMENT de générer des scénarios (ex: 'génère les scénarios', 'crée les scénarios', 'lance la génération'). Aide-le plutôt à affiner son contexte historique, ses notes de projet, à sélectionner ses sources audio, et à enrichir son brief. N'anticipe pas ses demandes - attends qu'il te le demande clairement.",
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
