"""Pytest fixtures and stubs shared across tests."""

import sys
import types


def _ensure_anthropic_stub() -> None:
    try:
        import anthropic  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    module = types.ModuleType("anthropic")

    class _DummyMessages:
        def create(self, *args, **kwargs):
            return {"content": [], "stop_reason": "end_turn"}

        def stream(self, *args, **kwargs):
            class _DummyStream:
                def __enter__(self):
                    return []

                def __exit__(self, exc_type, exc, tb):
                    return False

            return _DummyStream()

    class DummyAnthropic:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.messages = _DummyMessages()

    class _DummyError(Exception):
        pass

    module.Anthropic = DummyAnthropic
    module.AuthenticationError = _DummyError
    module.RateLimitError = _DummyError
    module.APIError = _DummyError
    sys.modules["anthropic"] = module


_ensure_anthropic_stub()


def _ensure_qwen_stub() -> None:
    try:
        import qwen_tts  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    module = types.ModuleType("qwen_tts")

    class _DummyModel:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

        def generate_voice_design(self, text: str, language: str, instruct: str):
            import numpy as np

            wav = np.zeros(16000, dtype=np.float32)
            return [wav], 16000

    module.Qwen3TTSModel = _DummyModel
    sys.modules["qwen_tts"] = module


_ensure_qwen_stub()
