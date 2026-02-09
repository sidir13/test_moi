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
