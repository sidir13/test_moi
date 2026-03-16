"""
Tests for get_audio_info.py
Covers: get_audio_info
Location: src/memoiredesterritoires/audio/get_audio_info.py
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock


# ════════════════════════════════════════════════════════════════
# CONSTANTES & FIXTURES
# ════════════════════════════════════════════════════════════════

SR = 22050
DURATION_S = 2.0
N_SAMPLES = int(SR * DURATION_S)

MODULE = "src.memoiredesterritoires.get_audio_info.get_audio_info"


@pytest.fixture
def mono_signal():
    """Signal mono synthétique 2s à amplitude contrôlée."""
    rng = np.random.default_rng(42)
    return rng.uniform(-0.5, 0.5, N_SAMPLES).astype(np.float32)


@pytest.fixture
def stereo_signal():
    """Signal stéréo synthétique 2s (2 canaux)."""
    rng = np.random.default_rng(42)
    return rng.uniform(-0.5, 0.5, (2, N_SAMPLES)).astype(np.float32)


@pytest.fixture
def audio_file(tmp_path):
    """Fichier .wav vide mais existant sur le disque (lecture mockée via librosa)."""
    f = tmp_path / "narration.wav"
    f.touch()
    return f


@pytest.fixture
def frame_rms_mock():
    """
    Simule la sortie de librosa.feature.rms : shape (1, n_frames).
    Valeurs croissantes pour que noise_floor < signal_level de façon déterministe.
    """
    frames = np.linspace(0.01, 0.5, 100).astype(np.float32)
    return frames[np.newaxis, :]  # shape (1, 100)


# ════════════════════════════════════════════════════════════════
# 1. IMPORT
# ════════════════════════════════════════════════════════════════

class TestImport:

    def test_function_importable(self):
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info
        assert callable(get_audio_info)

    def test_no_side_effects_on_import(self):
        """Importer le module ne doit pas déclencher d'exécution de code."""
        import importlib
        mod = importlib.import_module("src.memoiredesterritoires.get_audio_info.get_audio_info")
        assert hasattr(mod, "get_audio_info")


# ════════════════════════════════════════════════════════════════
# 2. GESTION DES ERREURS
# ════════════════════════════════════════════════════════════════

class TestErrorHandling:

    def test_raises_file_not_found_string_path(self, tmp_path):
        """Lève FileNotFoundError si le chemin (str) n'existe pas."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with pytest.raises(FileNotFoundError) as exc_info:
            get_audio_info(str(tmp_path / "inexistant.wav"))

        assert "introuvable" in str(exc_info.value).lower()

    def test_raises_file_not_found_path_object(self, tmp_path):
        """Lève FileNotFoundError si le chemin (Path) n'existe pas."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with pytest.raises(FileNotFoundError):
            get_audio_info(tmp_path / "inexistant.wav")

    def test_error_message_contains_path(self, tmp_path):
        """Le message d'erreur doit mentionner le chemin fautif."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        bad_path = tmp_path / "missing.wav"
        with pytest.raises(FileNotFoundError) as exc_info:
            get_audio_info(bad_path)

        assert "missing.wav" in str(exc_info.value)

    def test_does_not_raise_when_file_exists(self, audio_file, mono_signal, frame_rms_mock):
        """Aucune exception si le fichier existe (lecture mockée)."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert result is not None


# ════════════════════════════════════════════════════════════════
# 3. STRUCTURE DU RÉSULTAT
# ════════════════════════════════════════════════════════════════

class TestReturnStructure:

    EXPECTED_KEYS = {
        "status", "file", "duration_s", "sample_rate", "channels",
        "n_samples", "rms_db", "peak_db", "dynamic_range_db", "snr_estimate_db"
    }

    def test_returns_dict(self, audio_file, mono_signal, frame_rms_mock):
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert isinstance(result, dict)

    def test_all_expected_keys_present(self, audio_file, mono_signal, frame_rms_mock):
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert self.EXPECTED_KEYS.issubset(result.keys())

    def test_no_extra_none_values(self, audio_file, mono_signal, frame_rms_mock):
        """Aucune valeur retournée ne doit être None."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        for key in self.EXPECTED_KEYS:
            assert result[key] is not None, f"Clé '{key}' est None"

    def test_status_is_ok(self, audio_file, mono_signal, frame_rms_mock):
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert result["status"] == "ok"

    def test_file_key_contains_path(self, audio_file, mono_signal, frame_rms_mock):
        """La clé 'file' doit contenir le chemin du fichier analysé."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert "narration.wav" in result["file"]


# ════════════════════════════════════════════════════════════════
# 4. DÉTECTION MONO / STÉRÉO
# ════════════════════════════════════════════════════════════════

class TestChannelDetection:

    def test_mono_signal_returns_channels_1(self, audio_file, mono_signal, frame_rms_mock):
        """Un signal 1D (mono) doit retourner channels=1."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        assert mono_signal.ndim == 1  # vérification fixture

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert result["channels"] == 1

    def test_stereo_signal_returns_channels_2(self, audio_file, stereo_signal, frame_rms_mock):
        """Un signal 2D (stéréo) doit retourner channels=2."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        assert stereo_signal.ndim == 2  # vérification fixture
        mono_from_stereo = stereo_signal.mean(axis=0)

        with patch("librosa.load", return_value=(stereo_signal, SR)), \
             patch("librosa.to_mono", return_value=mono_from_stereo), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert result["channels"] == 2

    def test_stereo_calls_librosa_to_mono(self, audio_file, stereo_signal, frame_rms_mock):
        """Pour un signal stéréo, librosa.to_mono doit être appelé une fois."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        mono_from_stereo = stereo_signal.mean(axis=0)
        mock_to_mono = MagicMock(return_value=mono_from_stereo)

        with patch("librosa.load", return_value=(stereo_signal, SR)), \
             patch("librosa.to_mono", mock_to_mono), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            get_audio_info(audio_file)

        mock_to_mono.assert_called_once()

    def test_mono_does_not_call_librosa_to_mono(self, audio_file, mono_signal, frame_rms_mock):
        """Pour un signal mono, librosa.to_mono ne doit PAS être appelé."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        mock_to_mono = MagicMock()

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.to_mono", mock_to_mono), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            get_audio_info(audio_file)

        mock_to_mono.assert_not_called()


# ════════════════════════════════════════════════════════════════
# 5. CALCULS TECHNIQUES
# ════════════════════════════════════════════════════════════════

class TestComputations:

    def test_duration_s_is_correct(self, audio_file, mono_signal, frame_rms_mock):
        """duration_s = n_samples / sr, arrondi à 3 décimales."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        expected = round(len(mono_signal) / SR, 3)

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert result["duration_s"] == expected

    def test_n_samples_is_correct(self, audio_file, mono_signal, frame_rms_mock):
        """n_samples doit correspondre exactement à len(signal)."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert result["n_samples"] == len(mono_signal)

    def test_sample_rate_preserved(self, audio_file, mono_signal, frame_rms_mock):
        """Le sample_rate retourné doit être celui du fichier source (sr=None)."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, 44100)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert result["sample_rate"] == 44100

    def test_rms_db_matches_formula(self, audio_file, mono_signal, frame_rms_mock):
        """rms_db doit correspondre à 20*log10(sqrt(mean(y²)) + 1e-10), arrondi 2 déc."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        rms_linear = float(np.sqrt(np.mean(mono_signal ** 2)))
        expected_rms_db = round(float(20 * np.log10(rms_linear + 1e-10)), 2)

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert result["rms_db"] == expected_rms_db

    def test_peak_db_matches_formula(self, audio_file, mono_signal, frame_rms_mock):
        """peak_db doit correspondre à 20*log10(max(|y|) + 1e-10), arrondi 2 déc."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        peak_linear = float(np.max(np.abs(mono_signal)))
        expected_peak_db = round(float(20 * np.log10(peak_linear + 1e-10)), 2)

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert result["peak_db"] == expected_peak_db

    def test_dynamic_range_db_equals_peak_minus_rms(self, audio_file, mono_signal, frame_rms_mock):
        """dynamic_range_db = peak_db - rms_db."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        expected = round(result["peak_db"] - result["rms_db"], 2)
        assert result["dynamic_range_db"] == expected

    def test_dynamic_range_is_positive(self, audio_file, mono_signal, frame_rms_mock):
        """La plage dynamique doit toujours être positive (pic >= RMS)."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert result["dynamic_range_db"] >= 0

    def test_snr_estimate_db_is_positive_for_clean_signal(self, audio_file, frame_rms_mock):
        """Pour un signal propre (faible bruit de plancher), le SNR doit être positif."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        # Signal propre : valeurs RMS croissantes → noise_floor << signal_level
        clean_signal = np.sin(2 * np.pi * 440 * np.arange(N_SAMPLES) / SR).astype(np.float32)
        clean_frames = np.linspace(0.001, 0.8, 100).astype(np.float32)[np.newaxis, :]

        with patch("librosa.load", return_value=(clean_signal, SR)), \
             patch("librosa.feature.rms", return_value=clean_frames):
            result = get_audio_info(audio_file)

        assert result["snr_estimate_db"] > 0

    def test_snr_uses_librosa_feature_rms(self, audio_file, mono_signal, frame_rms_mock):
        """librosa.feature.rms doit être appelé exactement une fois."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        mock_rms = MagicMock(return_value=frame_rms_mock)

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", mock_rms):
            get_audio_info(audio_file)

        mock_rms.assert_called_once()

    def test_librosa_load_called_with_sr_none(self, audio_file, mono_signal, frame_rms_mock):
        """librosa.load doit être appelé avec sr=None pour préserver le SR natif."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        mock_load = MagicMock(return_value=(mono_signal, SR))

        with patch("librosa.load", mock_load), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            get_audio_info(audio_file)

        _, kwargs = mock_load.call_args
        assert kwargs.get("sr") is None

    def test_librosa_load_called_with_mono_false(self, audio_file, mono_signal, frame_rms_mock):
        """librosa.load doit être appelé avec mono=False pour détecter la stéréo."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        mock_load = MagicMock(return_value=(mono_signal, SR))

        with patch("librosa.load", mock_load), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            get_audio_info(audio_file)

        _, kwargs = mock_load.call_args
        assert kwargs.get("mono") is False


# ════════════════════════════════════════════════════════════════
# 6. FORMATS D'ENTRÉE
# ════════════════════════════════════════════════════════════════

class TestInputFormats:

    def test_accepts_string_path(self, audio_file, mono_signal, frame_rms_mock):
        """La fonction doit accepter un chemin sous forme de str."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(str(audio_file))

        assert result["status"] == "ok"

    def test_accepts_path_object(self, audio_file, mono_signal, frame_rms_mock):
        """La fonction doit accepter un objet Path."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(Path(audio_file))

        assert result["status"] == "ok"

    @pytest.mark.parametrize("extension", [".wav", ".mp3", ".flac", ".ogg"])
    def test_accepts_various_audio_extensions(self, tmp_path, mono_signal, frame_rms_mock, extension):
        """La fonction doit accepter les formats audio courants (lecture mockée)."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        f = tmp_path / f"audio{extension}"
        f.touch()

        with patch("librosa.load", return_value=(mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(f)

        assert result["status"] == "ok"


# ════════════════════════════════════════════════════════════════
# 7. VALEURS LIMITES
# ════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_silent_signal_does_not_raise(self, audio_file, frame_rms_mock):
        """Un signal silencieux (tous zéros) ne doit pas lever d'exception."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        silent = np.zeros(N_SAMPLES, dtype=np.float32)
        silent_frames = np.full((1, 100), 1e-10, dtype=np.float32)

        with patch("librosa.load", return_value=(silent, SR)), \
             patch("librosa.feature.rms", return_value=silent_frames):
            result = get_audio_info(audio_file)

        assert result["status"] == "ok"

    def test_silent_signal_rms_is_very_low(self, audio_file):
        """Un signal silencieux doit avoir un rms_db très bas (proche de -200 dB)."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        silent = np.zeros(N_SAMPLES, dtype=np.float32)
        silent_frames = np.full((1, 100), 1e-10, dtype=np.float32)

        with patch("librosa.load", return_value=(silent, SR)), \
             patch("librosa.feature.rms", return_value=silent_frames):
            result = get_audio_info(audio_file)

        assert result["rms_db"] < -100

    def test_very_short_signal(self, audio_file, frame_rms_mock):
        """Un signal très court (100 samples) doit être traité sans erreur."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        short_signal = np.random.uniform(-0.5, 0.5, 100).astype(np.float32)

        with patch("librosa.load", return_value=(short_signal, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert result["n_samples"] == 100

    def test_high_sample_rate_preserved(self, audio_file, mono_signal, frame_rms_mock):
        """Un SR de 96 000 Hz doit être conservé tel quel dans le résultat."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        with patch("librosa.load", return_value=(mono_signal, 96000)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        assert result["sample_rate"] == 96000

    def test_full_scale_signal_peak_near_0_db(self, audio_file, frame_rms_mock):
        """Un signal full scale (amplitude max 1.0) doit avoir un peak_db proche de 0."""
        from src.memoiredesterritoires.get_audio_info.get_audio_info import get_audio_info

        full_scale = np.ones(N_SAMPLES, dtype=np.float32)

        with patch("librosa.load", return_value=(full_scale, SR)), \
             patch("librosa.feature.rms", return_value=frame_rms_mock):
            result = get_audio_info(audio_file)

        # 20 * log10(1.0 + 1e-10) ≈ 0
        assert abs(result["peak_db"]) < 0.01
