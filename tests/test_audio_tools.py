"""
Tests for audio_tools.py
Covers: adjust_audio_volume, mix_voice_with_noise, mix_voice_with_background
Location: src/memoiredesterritoires/audio/audio_tools.py
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock


# ════════════════════════════════════════════════════════════════
# FIXTURES PARTAGÉES
# ════════════════════════════════════════════════════════════════

SR = 22050


@pytest.fixture
def dummy_mono_signal():
    """Signal mono synthétique de 2 secondes."""
    return np.random.uniform(-0.5, 0.5, SR * 2).astype(np.float32)


@pytest.fixture
def dummy_voice_file(tmp_path):
    f = tmp_path / "narration.wav"
    f.write_bytes(b"RIFF")
    return f


@pytest.fixture
def dummy_noise_file(tmp_path):
    f = tmp_path / "noise.wav"
    f.write_bytes(b"RIFF")
    return f


@pytest.fixture
def dummy_background_file(tmp_path):
    f = tmp_path / "ambiance.wav"
    f.write_bytes(b"RIFF")
    return f


# ════════════════════════════════════════════════════════════════
# 1. TESTS : adjust_audio_volume
# ════════════════════════════════════════════════════════════════

class TestAdjustAudioVolume:

    def test_import(self):
        from src.memoiredesterritoires.audio_tools.audio_tools import adjust_audio_volume
        assert adjust_audio_volume is not None

    def test_returns_expected_keys(self, dummy_voice_file, dummy_mono_signal, tmp_path):
        from src.memoiredesterritoires.audio_tools.audio_tools import adjust_audio_volume

        out = tmp_path / "output.wav"

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=np.array([[0.1, 0.12]])), \
             patch("librosa.amplitude_to_db", return_value=np.array([-20.0])), \
             patch("soundfile.write"):

            result = adjust_audio_volume(dummy_voice_file, out, gain_db=0.0)

        expected_keys = {
            "status", "input_file", "output_file", "sample_rate",
            "gain_db", "rms_before_db", "rms_after_db", "max_amplitude"
        }
        assert expected_keys.issubset(result.keys())

    def test_status_saved(self, dummy_voice_file, dummy_mono_signal, tmp_path):
        from src.memoiredesterritoires.audio_tools.audio_tools import adjust_audio_volume

        out = tmp_path / "output.wav"

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=np.array([[0.1, 0.2]])), \
             patch("librosa.amplitude_to_db", return_value=np.array([-20.0])), \
             patch("soundfile.write"):

            result = adjust_audio_volume(dummy_voice_file, out, gain_db=0.0)

        assert result["status"] == "saved"

    def test_gain_zero_db_unchanged_amplitude(self, dummy_voice_file, dummy_mono_signal, tmp_path):
        """Un gain de 0 dB ne doit pas modifier le signal."""
        from src.memoiredesterritoires.audio_tools.audio_tools import adjust_audio_volume

        out = tmp_path / "output.wav"
        captured = {}

        def fake_write(path, data, sr):
            captured["data"] = data

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=np.array([[0.1, 0.2]])), \
             patch("librosa.amplitude_to_db", return_value=np.array([-20.0])), \
             patch("soundfile.write", side_effect=fake_write):

            adjust_audio_volume(dummy_voice_file, out, gain_db=0.0)

        np.testing.assert_allclose(captured["data"], dummy_mono_signal)

    def test_positive_gain_increases_amplitude(self, dummy_voice_file, dummy_mono_signal, tmp_path):
        """Un gain positif doit augmenter l'amplitude du signal."""
        from src.memoiredesterritoires.audio_tools.audio_tools import adjust_audio_volume

        out = tmp_path / "output.wav"
        captured = {}

        def fake_write(path, data, sr):
            captured["data"] = data

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=np.array([[0.1, 0.2]])), \
             patch("librosa.amplitude_to_db", return_value=np.array([-20.0])), \
             patch("soundfile.write", side_effect=fake_write):

            adjust_audio_volume(dummy_voice_file, out, gain_db=6.0)

        assert np.max(np.abs(captured["data"])) > np.max(np.abs(dummy_mono_signal))

    def test_negative_gain_decreases_amplitude(self, dummy_voice_file, dummy_mono_signal, tmp_path):
        """Un gain négatif doit réduire l'amplitude du signal."""
        from src.memoiredesterritoires.audio_tools.audio_tools import adjust_audio_volume

        out = tmp_path / "output.wav"
        captured = {}

        def fake_write(path, data, sr):
            captured["data"] = data

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=np.array([[0.1, 0.2]])), \
             patch("librosa.amplitude_to_db", return_value=np.array([-20.0])), \
             patch("soundfile.write", side_effect=fake_write):

            adjust_audio_volume(dummy_voice_file, out, gain_db=-6.0)

        assert np.max(np.abs(captured["data"])) < np.max(np.abs(dummy_mono_signal))

    def test_output_file_is_written(self, dummy_voice_file, dummy_mono_signal, tmp_path):
        """soundfile.write doit être appelé avec le bon chemin de sortie."""
        from src.memoiredesterritoires.audio_tools.audio_tools import adjust_audio_volume

        out = tmp_path / "output.wav"
        mock_write = MagicMock()

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
            patch("librosa.feature.rms", return_value=np.array([[0.1]])), \
            patch("librosa.amplitude_to_db", return_value=np.array([-20.0])), \
            patch("soundfile.write", mock_write):

            adjust_audio_volume(dummy_voice_file, out, gain_db=3.0)

        mock_write.assert_called_once()
        # Comparaison sur le vrai argument, pas sa repr string
        actual_path = mock_write.call_args[0][0]
        assert str(actual_path) == str(out)


# ════════════════════════════════════════════════════════════════
# 2. TESTS : mix_voice_with_noise
# ════════════════════════════════════════════════════════════════

class TestMixVoiceWithNoise:

    def test_import(self):
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_noise
        assert mix_voice_with_noise is not None

    def test_raises_if_voice_not_found(self, dummy_noise_file, tmp_path):
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_noise
        with pytest.raises(FileNotFoundError, match="voix"):
            mix_voice_with_noise(
                voice_file="inexistant.wav",
                noise_file=dummy_noise_file,
                output_file=tmp_path / "out.wav"
            )

    def test_raises_if_noise_not_found(self, dummy_voice_file, tmp_path):
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_noise
        with pytest.raises(FileNotFoundError, match="son"):
            mix_voice_with_noise(
                voice_file=dummy_voice_file,
                noise_file="inexistant.wav",
                output_file=tmp_path / "out.wav"
            )

    def test_returns_expected_keys(self, dummy_voice_file, dummy_noise_file, dummy_mono_signal, tmp_path):
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_noise

        out = tmp_path / "mixed.wav"

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("soundfile.write"):

            result = mix_voice_with_noise(
                voice_file=dummy_voice_file,
                noise_file=dummy_noise_file,
                output_file=out,
                snr_db=15,
                start_time=0.5,
                noise_duration=1.0,
            )

        expected_keys = {
            "status", "voice_file", "noise_file", "output_file", "sample_rate",
            "snr_db", "start_time", "noise_duration", "actual_snr"
        }
        assert expected_keys.issubset(result.keys())

    def test_status_mixed(self, dummy_voice_file, dummy_noise_file, dummy_mono_signal, tmp_path):
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_noise

        out = tmp_path / "mixed.wav"

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("soundfile.write"):

            result = mix_voice_with_noise(
                voice_file=dummy_voice_file,
                noise_file=dummy_noise_file,
                output_file=out,
                start_time=0.0,
                noise_duration=1.0,
            )

        assert result["status"] == "mixed"

    def test_resampling_triggered_on_sr_mismatch(
            self, dummy_voice_file, dummy_noise_file, dummy_mono_signal, tmp_path
    ):
        """librosa.resample doit être appelé si les SR sont différents."""
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_noise

        out = tmp_path / "mixed.wav"
        noise_signal = np.random.uniform(-0.3, 0.3, SR).astype(np.float32)

        def load_side_effect(path, sr=None, **kwargs):
            if "narration" in str(path):
                return dummy_mono_signal, SR
            return noise_signal, 44100

        mock_resample = MagicMock(return_value=noise_signal)

        with patch("librosa.load", side_effect=load_side_effect), \
             patch("librosa.resample", mock_resample), \
             patch("soundfile.write"):

            mix_voice_with_noise(
                voice_file=dummy_voice_file,
                noise_file=dummy_noise_file,
                output_file=out,
                start_time=0.0,
                noise_duration=1.0,
            )

        mock_resample.assert_called_once()

    def test_output_not_saturated(self, dummy_voice_file, dummy_noise_file, dummy_mono_signal, tmp_path):
        """Le signal de sortie ne doit pas dépasser 1.0 en amplitude."""
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_noise

        out = tmp_path / "mixed.wav"
        captured = {}

        def fake_write(path, data, sr):
            captured["data"] = data

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("soundfile.write", side_effect=fake_write):

            mix_voice_with_noise(
                voice_file=dummy_voice_file,
                noise_file=dummy_noise_file,
                output_file=out,
                snr_db=5,
                start_time=0.0,
                noise_duration=1.0,
            )

        assert np.max(np.abs(captured["data"])) <= 1.0

    def test_snr_params_preserved_in_output(self, dummy_voice_file, dummy_noise_file, dummy_mono_signal, tmp_path):
        """Les paramètres snr_db, fade_in_s et fade_out_s doivent figurer dans le résultat."""
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_noise

        out = tmp_path / "mixed.wav"

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("soundfile.write"):

            result = mix_voice_with_noise(
                voice_file=dummy_voice_file,
                noise_file=dummy_noise_file,
                output_file=out,
                snr_db=20,
                fade_in_s=0.5,
                fade_out_s=0.8,
                start_time=0.0,
                noise_duration=1.0,
            )

        assert result["snr_db"] == 20
        assert result["fade_in_s"] == 0.5
        assert result["fade_out_s"] == 0.8


# ════════════════════════════════════════════════════════════════
# 3. TESTS : mix_voice_with_background
# ════════════════════════════════════════════════════════════════

class TestMixVoiceWithBackground:

    def test_import(self):
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_background
        assert mix_voice_with_background is not None

    def test_returns_expected_keys(self, dummy_voice_file, dummy_background_file, dummy_mono_signal, tmp_path):
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_background

        out = tmp_path / "final_mix.wav"

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=np.array([[0.1, 0.12]])), \
             patch("librosa.amplitude_to_db", return_value=np.array([-20.0])), \
             patch("soundfile.write"):

            result = mix_voice_with_background(
                voice_file=dummy_voice_file,
                background_file=dummy_background_file,
                output_file=out,
            )

        expected_keys = {
            "status", "voice_file", "background_file", "output_file", "sample_rate",
            "voice_bg_ratio_db", "rms_voice_db", "rms_bg_before_db",
            "rms_bg_after_db", "gain_applied_db", "duration_s"
        }
        assert expected_keys.issubset(result.keys())

    def test_status_saved(self, dummy_voice_file, dummy_background_file, dummy_mono_signal, tmp_path):
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_background

        out = tmp_path / "final_mix.wav"

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=np.array([[0.1]])), \
             patch("librosa.amplitude_to_db", return_value=np.array([-20.0])), \
             patch("soundfile.write"):

            result = mix_voice_with_background(
                voice_file=dummy_voice_file,
                background_file=dummy_background_file,
                output_file=out,
            )

        assert result["status"] == "saved"

    def test_background_looped_if_too_short(self, dummy_voice_file, dummy_background_file, tmp_path):
        """Si le fond est plus court que la voix, il doit être bouclé."""
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_background

        voice = np.random.uniform(-0.3, 0.3, SR * 10).astype(np.float32)
        bg    = np.random.uniform(-0.1, 0.1, SR * 2).astype(np.float32)

        out = tmp_path / "final_mix.wav"
        captured = {}

        def fake_write(path, data, sr):
            captured["data"] = data

        with patch("librosa.load", side_effect=[(voice, SR), (bg, SR)]), \
             patch("librosa.feature.rms", return_value=np.array([[0.1]])), \
             patch("librosa.amplitude_to_db", return_value=np.array([-20.0])), \
             patch("soundfile.write", side_effect=fake_write):

            mix_voice_with_background(
                voice_file=dummy_voice_file,
                background_file=dummy_background_file,
                output_file=out,
            )

        assert len(captured["data"]) == len(voice)

    def test_output_not_saturated(self, dummy_voice_file, dummy_background_file, dummy_mono_signal, tmp_path):
        """Le mix final ne doit pas saturer (amplitude ≤ 1.0)."""
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_background

        out = tmp_path / "final_mix.wav"
        captured = {}

        def fake_write(path, data, sr):
            captured["data"] = data

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=np.array([[0.1]])), \
             patch("librosa.amplitude_to_db", return_value=np.array([-20.0])), \
             patch("soundfile.write", side_effect=fake_write):

            mix_voice_with_background(
                voice_file=dummy_voice_file,
                background_file=dummy_background_file,
                output_file=out,
                voice_bg_ratio_db=0.0,
            )

        assert np.max(np.abs(captured["data"])) <= 1.0

    def test_ratio_params_preserved(self, dummy_voice_file, dummy_background_file, dummy_mono_signal, tmp_path):
        from src.memoiredesterritoires.audio_tools.audio_tools import mix_voice_with_background

        out = tmp_path / "final_mix.wav"

        with patch("librosa.load", return_value=(dummy_mono_signal, SR)), \
             patch("librosa.feature.rms", return_value=np.array([[0.1]])), \
             patch("librosa.amplitude_to_db", return_value=np.array([-20.0])), \
             patch("soundfile.write"):

            result = mix_voice_with_background(
                voice_file=dummy_voice_file,
                background_file=dummy_background_file,
                output_file=out,
                voice_bg_ratio_db=-18.0,
                fade_in_s=3.0,
                fade_out_s=3.0,
            )

        assert result["voice_bg_ratio_db"] == -18.0
        assert result["fade_in_s"] == 3.0
        assert result["fade_out_s"] == 3.0
