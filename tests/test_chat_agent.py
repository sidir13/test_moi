import importlib.util
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

CHAT_AGENT_PATH = Path(__file__).resolve().parents[1] / "src" / "server" / "chat_agent.py"
chat_agent_module = None


def _load_chat_agent():
    main_backup = sys.modules.get("main")
    if not main_backup:
        main_stub = types.ModuleType("main")
        main_stub.TOOLS = []
        main_stub.build_skill_context = lambda skills: "<skills>"
        main_stub.check_available_skills = lambda: []
        main_stub.execute_tool = lambda name, payload: {"tool": name, "input": payload}
        sys.modules["main"] = main_stub

    spec = importlib.util.spec_from_file_location("chat_agent_module", CHAT_AGENT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore

    if main_backup:
        sys.modules["main"] = main_backup
    else:
        sys.modules.pop("main", None)

    global chat_agent_module
    chat_agent_module = module
    return module.ChatAgent


ChatAgent = _load_chat_agent()


class DummySessionStore:
    def __init__(self):
        self._history = {}

    def get_chat_history(self, session_id):
        return self._history.get(session_id, [])

    def save_chat_history(self, session_id, history):
        self._history[session_id] = history


class DummyWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, payload):
        self.messages.append(payload)


class DummyAnthropicClient:
    class _Messages:
        def create(self, **kwargs):
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text="Bonjour")],
            )

    def __init__(self, **kwargs):
        self.messages = self._Messages()


@pytest.mark.asyncio
async def test_chat_agent_streams_reply(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(chat_agent_module, "Anthropic", DummyAnthropicClient)

    agent = ChatAgent()
    store = DummySessionStore()
    ws = DummyWebSocket()

    await agent.handle_message("session-1", "Salut", store, ws)

    assert {"type": "assistant_text", "text": "Bonjour"} in ws.messages
    assert ws.messages[-1] == {"type": "done"}
