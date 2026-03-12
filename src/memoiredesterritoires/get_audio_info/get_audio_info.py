from pathlib import Path
import logging
import librosa
import numpy as np

logger = logging.getLogger(__name__)


def get_audio_info(audio_file: Path | str) -> dict:
    """
    Analyse un fichier audio et retourne ses informations techniques.
    Utile pour que le LLM raisonne sur les timestamps et niveaux avant de mixer.

    Args:
        audio_file: Chemin du fichier audio à analyser

    Returns:
        Dictionnaire avec toutes les métadonnées du fichier

    Example:
        >>> get_audio_info("data/audio/narration.wav")
        {
            "status": "ok",
            "file": "narration.wav",
            "duration_s": 45.3,
            "sample_rate": 44100,
            "channels": 1,
            "n_samples": 1997730,
            "rms_db": -24.12,
            "peak_db": -3.45,
            "dynamic_range_db": 20.67,
            "snr_estimate_db": 18.4,
        }
    """
    logger.info("🔍 ANALYSE AUDIO — %s", audio_file)

    audio_path = Path(audio_file)

    if not audio_path.exists():
        logger.error("Fichier introuvable : %s", audio_path)
        raise FileNotFoundError(f"Fichier introuvable : {audio_path}")

    y, sr = librosa.load(str(audio_path), sr=None, mono=False)

    if y.ndim == 1:
        channels, y_mono = 1, y
    else:
        channels, y_mono = y.shape[0], librosa.to_mono(y)

    duration_s       = len(y_mono) / sr
    n_samples        = len(y_mono)
    rms_linear       = float(np.sqrt(np.mean(y_mono ** 2)))
    rms_db           = float(20 * np.log10(rms_linear + 1e-10))
    peak_linear      = float(np.max(np.abs(y_mono)))
    peak_db          = float(20 * np.log10(peak_linear + 1e-10))
    dynamic_range_db = round(peak_db - rms_db, 2)

    frame_rms    = librosa.feature.rms(y=y_mono)[0]
    sorted_rms   = np.sort(frame_rms)
    noise_floor  = float(np.mean(sorted_rms[:max(1, len(sorted_rms) // 10)]))
    signal_level = float(np.mean(sorted_rms[len(sorted_rms) // 2:]))
    snr_estimate = float(20 * np.log10((signal_level + 1e-10) / (noise_floor + 1e-10)))

    logger.info("📁 Fichier     : %s", audio_path.name)
    logger.info("⏱️  Durée       : %.2fs", duration_s)
    logger.info("🎛️  Sample rate : %d Hz  |  Canaux : %d", sr, channels)
    logger.info("📊 RMS         : %.2f dB", rms_db)
    logger.info("📈 Pic         : %.2f dB", peak_db)
    logger.info("🌊 Plage dyn.  : %.2f dB", dynamic_range_db)
    logger.info("📡 SNR estimé  : %.2f dB", snr_estimate)

    result = {
        "status":           "ok",
        "file":             str(audio_path),
        "duration_s":       round(duration_s, 3),
        "sample_rate":      sr,
        "channels":         channels,
        "n_samples":        n_samples,
        "rms_db":           round(rms_db, 2),
        "peak_db":          round(peak_db, 2),
        "dynamic_range_db": dynamic_range_db,
        "snr_estimate_db":  round(snr_estimate, 2),
    }

    logger.debug("Résultat complet : %s", result)
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    info = get_audio_info("data/audio/narration.wav")
