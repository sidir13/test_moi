import sys
import types
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _ensure_qwen_stub():
    if "qwen_tts" in sys.modules:
        return

    module = types.ModuleType("qwen_tts")

    class _DummyModel:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

        def generate_voice_design(self, text: str, language: str, instruct: str):
            wav = [0.0] * 16000
            return [wav], 16000

    module.Qwen3TTSModel = _DummyModel
    sys.modules["qwen_tts"] = module


_ensure_qwen_stub()


module = import_module(
    "memoiredesterritoires.text_to_speech_with_instructions.text_to_speech_with_instructions"
)


def test_resolve_prefers_explicit_local_path(tmp_path):
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir(parents=True)

    source, kwargs = module._resolve_model_source(str(custom_dir))

    assert source == str(custom_dir)
    assert kwargs.get("local_files_only") is True


def test_resolve_uses_cached_dir(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "weights.safetensors").write_text("stub", encoding="utf-8")
    monkeypatch.setattr(module, "LOCAL_MODEL_DIR", cache_dir)

    source, kwargs = module._resolve_model_source(module.DEFAULT_MODEL)

    assert source == str(cache_dir)
    assert kwargs.get("local_files_only") is True


def test_resolve_remote_with_cache_dir(tmp_path, monkeypatch):
    cache_dir = tmp_path / "empty"
    monkeypatch.setattr(module, "LOCAL_MODEL_DIR", cache_dir)

    source, kwargs = module._resolve_model_source(module.DEFAULT_MODEL)

    assert source == module.DEFAULT_MODEL
    assert kwargs.get("cache_dir") == str(cache_dir)
    assert cache_dir.exists()
