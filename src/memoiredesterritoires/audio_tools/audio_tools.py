from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional
import logging
import librosa
import soundfile as sf
import numpy as np

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS      = {".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aac"}
BACKGROUND_SOUNDS_DIR = Path("data/eng")

FadeType = Literal["linear", "exponential", "logarithmic", "equal_power", "sigmoid"]


# ════════════════════════════════════════════════════════════════
# UTILITAIRE INTERNE : _apply_fade
# ════════════════════════════════════════════════════════════════

def _apply_fade(
    signal: np.ndarray,
    sr: int,
    fade_in_s: float   = 0.0,
    fade_out_s: float  = 0.0,
    fade_in_type:  FadeType = "logarithmic",
    fade_out_type: FadeType = "exponential",
) -> np.ndarray:
    """
    Applique des fondus d'entrée et/ou de sortie sur un signal.

    Courbes disponibles :
        linear       → t           (transitions brusques, SFX courts)
        exponential  → t²          (⭐ fade OUT standard)
        logarithmic  → √t          (⭐ fade IN standard)
        equal_power  → sin/cos     (⭐ crossfade, volume constant)
        sigmoid      → 1/(1+e^-x)  (fondus longs, cinéma, ambiances)
    """
    result = signal.copy()
    n      = len(result)

    def _curve(t: np.ndarray, curve_type: FadeType) -> np.ndarray:
        if curve_type == "linear":
            return t
        elif curve_type == "exponential":
            return t ** 2
        elif curve_type == "logarithmic":
            return np.sqrt(np.clip(t, 0, 1))
        elif curve_type == "equal_power":
            return np.sin(t * np.pi / 2)
        elif curve_type == "sigmoid":
            return 1 / (1 + np.exp(-10 * (t - 0.5)))
        return t

    if fade_in_s > 0:
        n_in = min(int(fade_in_s * sr), n)
        result[:n_in] *= _curve(np.linspace(0, 1, n_in), fade_in_type)

    if fade_out_s > 0:
        n_out = min(int(fade_out_s * sr), n)
        t_out = np.linspace(1, 0, n_out)
        result[n - n_out:] *= _curve(t_out, fade_out_type)

    return result

def _find_audio_onset(y: np.ndarray, sr: int, threshold_db: float = -40.0) -> int:
    """Retourne l'index sample où le son dépasse le seuil (skip silence initial)."""
    frame_rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    rms_db    = 20 * np.log10(frame_rms + 1e-10)
    onset_frame = np.argmax(rms_db > threshold_db)
    return int(onset_frame * 512) 

# ════════════════════════════════════════════════════════════════
# 1. get_audio_info
# ════════════════════════════════════════════════════════════════

def get_audio_info(audio_file: Path | str) -> dict:
    """
    Analyse un fichier audio et retourne ses informations techniques.

    Args:
        audio_file: Chemin du fichier audio à analyser

    Returns:
        {status, file, duration_s, sample_rate, channels, n_samples,
         rms_db, peak_db, dynamic_range_db, snr_estimate_db}
    """
    logger.info("🔍 Analyse audio — %s", audio_file)

    audio_path = Path(audio_file)
    if not audio_path.exists():
        logger.error("Fichier introuvable : %s", audio_path)
        raise FileNotFoundError(f"Fichier introuvable : {audio_path}")

    y, sr = librosa.load(str(audio_path), sr=None, mono=False)

    if y.ndim == 1:
        channels, y_mono = 1, y
    else:
        channels, y_mono = y.shape[0], librosa.to_mono(y)

    duration_s  = len(y_mono) / sr
    rms_db      = float(20 * np.log10(np.sqrt(np.mean(y_mono ** 2)) + 1e-10))
    peak_db     = float(20 * np.log10(np.max(np.abs(y_mono)) + 1e-10))

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
    logger.info("🌊 Plage dyn.  : %.2f dB", round(peak_db - rms_db, 2))
    logger.info("📡 SNR estimé  : %.2f dB", snr_estimate)

    result = {
        "status":           "ok",
        "file":             str(audio_path),
        "duration_s":       round(duration_s, 3),
        "sample_rate":      sr,
        "channels":         channels,
        "n_samples":        len(y_mono),
        "rms_db":           round(rms_db, 2),
        "peak_db":          round(peak_db, 2),
        "dynamic_range_db": round(peak_db - rms_db, 2),
        "snr_estimate_db":  round(snr_estimate, 2),
    }
    logger.debug("Résultat complet : %s", result)
    return result


# ════════════════════════════════════════════════════════════════
# 2. find_background_sounds
# ════════════════════════════════════════════════════════════════

def find_background_sounds(keyword: Optional[str] = None, limit: int = 20) -> dict:
    """
    Retourne les chemins des sons disponibles, filtrés par mot-clé.

    Args:
        keyword: Mot-clé pour filtrer par nom de dossier
        limit:   Nombre maximum de résultats

    Returns:
        {status, root, keyword, limit, count, files}
    """
    if not BACKGROUND_SOUNDS_DIR.exists():
        logger.error("Répertoire sons introuvable : %s", BACKGROUND_SOUNDS_DIR)
        raise FileNotFoundError(f"Répertoire introuvable : {BACKGROUND_SOUNDS_DIR}")
    if limit <= 0:
        raise ValueError("limit doit être un entier positif")

    keyword_lower = keyword.lower() if keyword else None
    results: List[str] = []
    root_resolved = BACKGROUND_SOUNDS_DIR.resolve()

    for folder in sorted(root_resolved.iterdir()):
        if not folder.is_dir():
            continue
        if keyword_lower and keyword_lower not in folder.name.lower():
            continue
        for file in sorted(folder.rglob("*")):
            if file.is_file() and file.suffix.lower() in AUDIO_EXTENSIONS:
                rel_path = BACKGROUND_SOUNDS_DIR / file.relative_to(root_resolved)
                results.append(str(rel_path))
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break

    logger.info("🔎 Sons trouvés : keyword='%s'  →  %d résultat(s)", keyword, len(results))
    for f in results:
        logger.debug("   %s", f)

    return {
        "status":  "ok",
        "root":    str(BACKGROUND_SOUNDS_DIR),
        "keyword": keyword,
        "limit":   limit,
        "count":   len(results),
        "files":   results,
    }


# ════════════════════════════════════════════════════════════════
# 3. adjust_audio_volume
# ════════════════════════════════════════════════════════════════

def adjust_audio_volume(
    input_file:  Path | str,
    output_file: Path | str = Path("data/generated_speech/output.wav"),
    gain_db:     float = 0.0,
) -> dict:
    """
    Ajuste le volume d'un fichier audio en décibels.

    Args:
        input_file:  Fichier audio d'entrée
        output_file: Fichier audio de sortie
        gain_db:     Gain en dB (0 = inchangé, -3 = moitié puissance, +6 = double amplitude)

    Returns:
        {status, input_file, output_file, sample_rate, gain_db,
         rms_before_db, rms_after_db, max_amplitude}
    """
    logger.info("🔊 Ajustement volume — gain: %+.2f dB — %s", gain_db, input_file)

    input_path  = Path(input_file)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    y, sr      = librosa.load(str(input_path), sr=None)
    rms_before = float(np.mean(librosa.amplitude_to_db(librosa.feature.rms(y=y)[0])))
    gain       = 10 ** (gain_db / 20)
    y_adjusted = y * gain
    rms_after  = float(np.mean(librosa.amplitude_to_db(librosa.feature.rms(y=y_adjusted)[0])))
    max_amp    = float(np.max(np.abs(y_adjusted)))

    logger.info("📊 RMS : %.2f dB → %.2f dB", rms_before, rms_after)

    if max_amp > 1.0:
        logger.warning("⚠️  Saturation détectée (max: %.2f) — réduisez gain_db", max_amp)

    sf.write(str(output_path), y_adjusted, sr)
    logger.info("✓ Sauvegardé : %s", output_path)

    return {
        "status":        "saved",
        "input_file":    str(input_path),
        "output_file":   str(output_path),
        "sample_rate":   sr,
        "gain_db":       round(gain_db, 2),
        "rms_before_db": round(rms_before, 2),
        "rms_after_db":  round(rms_after, 2),
        "max_amplitude": round(max_amp, 4),
    }


# ════════════════════════════════════════════════════════════════
# 4. mix_voice_with_noise
# ════════════════════════════════════════════════════════════════

def mix_voice_with_noise(
    voice_file:         Path | str,
    noise_file:         Path | str,
    output_file:        Path | str   = Path("data/generated_speech/mixed_output.wav"),
    snr_db:             float        = 20,
    start_time:         float        = 0,
    noise_duration:     float | None = 3,
    noise_start_offset: float        = 0,
    fade_in_s:          float        = 2,
    fade_out_s:         float        = 2,
    fade_in_type:       FadeType     = "logarithmic",
    fade_out_type:      FadeType     = "exponential",
) -> dict:
    """
    Superpose un son ponctuel sur une voix avec contrôle SNR et fondus.

    Args:
        voice_file:         Fichier voix (base du mix)
        noise_file:         Fichier son à insérer
        output_file:        Fichier de sortie
        snr_db:             Rapport signal/bruit en dB (15 = voix 15 dB plus forte)
        start_time:         Timestamp (s) où le son démarre
        noise_duration:     Durée du son en secondes (None = jusqu'à la fin)
        noise_start_offset: Début de lecture dans le fichier son (s)
        fade_in_s:          Durée fade in (défaut 2s)
        fade_out_s:         Durée fade out (défaut 2s)
        fade_in_type:       Courbe fade in  (défaut : logarithmic ⭐)
        fade_out_type:      Courbe fade out (défaut : exponential  ⭐)

    Returns:
        {status, voice_file, noise_file, output_file, sample_rate,
         snr_db, start_time, noise_duration, actual_snr, ...}
    """
    logger.info("🎙️  Mixage voix + son ponctuel — t=%.2fs, snr=%ddB — %s",
                start_time, snr_db, noise_file)

    voice_path  = Path(voice_file)
    noise_path  = Path(noise_file)
    output_path = Path(output_file)

    if not voice_path.exists():
        logger.error("Fichier voix introuvable : %s", voice_path)
        raise FileNotFoundError(f"Fichier voix introuvable : {voice_path}")
    if not noise_path.exists():
        logger.error("Fichier son introuvable : %s", noise_path)
        raise FileNotFoundError(f"Fichier son introuvable : {noise_path}")

    voice, sr_voice = librosa.load(str(voice_path), sr=None)
    noise, sr_noise = librosa.load(str(noise_path), sr=None)

    logger.info("📁 Voix  : %s (%.2fs @ %dHz)", voice_path.name, len(voice)/sr_voice, sr_voice)
    logger.info("📁 Son   : %s (%.2fs @ %dHz)", noise_path.name, len(noise)/sr_noise, sr_noise)

    if sr_voice != sr_noise:
        logger.info("⚙️  Resampling : %dHz → %dHz", sr_noise, sr_voice)
        noise = librosa.resample(noise, orig_sr=sr_noise, target_sr=sr_voice)

    sr = sr_voice

    if noise_start_offset == 0:
        onset_sample = _find_audio_onset(noise, sr)
        if onset_sample > 0:
            logger.info("⏭️  Silence initial détecté → skip %.2fs", onset_sample / sr)
            noise = noise[onset_sample:]
    else:
        offset_sample = int(noise_start_offset * sr)
        if offset_sample >= len(noise):
            raise ValueError(
                f"Offset ({noise_start_offset}s) dépasse la durée du son ({len(noise)/sr:.2f}s)"
            )
        noise = noise[offset_sample:]

    start_sample = int(start_time * sr)
    available_length = int(noise_duration * sr) if noise_duration else len(voice) - start_sample
    end_sample   = min(start_sample + available_length, len(voice))

    rms_noise  = np.sqrt(np.mean(noise ** 2))
    voice_segment_rms = np.sqrt(np.mean(voice[start_sample:end_sample] ** 2))
    target_rms = voice_segment_rms / (10 ** (snr_db / 20))
    noise_gain = target_rms / (rms_noise + 1e-10)
    noise      = noise * noise_gain

    logger.info("🎚️  SNR cible : %d dB  |  Gain son : %.2f dB", snr_db, 20*np.log10(noise_gain))

    if len(noise) < available_length:
        repeats = int(np.ceil(available_length / len(noise)))
        noise   = np.tile(noise, repeats)
        logger.debug("🔁 Son bouclé x%d", repeats)

    noise_segment = _apply_fade(
        noise[:available_length], sr,
        fade_in_s=fade_in_s, fade_out_s=fade_out_s,
        fade_in_type=fade_in_type, fade_out_type=fade_out_type
    )
    logger.info("🎭 Fade in : %.2fs (%s)  |  Fade out : %.2fs (%s)",
                fade_in_s, fade_in_type, fade_out_s, fade_out_type)

    mixed      = voice.copy()
    end_sample = min(start_sample + len(noise_segment), len(mixed))
    actual_len = end_sample - start_sample
    mixed[start_sample:end_sample] += noise_segment[:actual_len]

    logger.info("🔀 Insertion : t=%.2fs → t=%.2fs (%.2fs)", start_time, end_sample/sr, actual_len/sr)

    max_amp = np.max(np.abs(mixed))
    if max_amp > 0.99:
        logger.warning("⚠️  Saturation → normalisation (max: %.3f)", max_amp)
        mixed = mixed / max_amp * 0.95

    rms_v_seg  = np.sqrt(np.mean(voice[start_sample:end_sample] ** 2))
    rms_n_seg  = np.sqrt(np.mean(noise_segment[:actual_len] ** 2))
    actual_snr = 20 * np.log10(rms_v_seg / (rms_n_seg + 1e-10))

    intelligibility = (
        "Excellente intelligibilité" if actual_snr >= 20 else
        "Bonne intelligibilité"      if actual_snr >= 10 else
        "Intelligibilité acceptable" if actual_snr >= 0  else
        "Intelligibilité difficile"
    )
    logger.info("✓ SNR final : %.2f dB — %s", actual_snr, intelligibility)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), mixed, sr)
    logger.info("💾 Sauvegardé : %s", output_path)

    return {
        "status":             "mixed",
        "voice_file":         str(voice_path),
        "noise_file":         str(noise_path),
        "output_file":        str(output_path),
        "sample_rate":        sr,
        "snr_db":             snr_db,
        "start_time":         start_time,
        "noise_duration":     noise_duration,
        "noise_start_offset": noise_start_offset,
        "fade_in_s":          fade_in_s,
        "fade_out_s":         fade_out_s,
        "fade_in_type":       fade_in_type,
        "fade_out_type":      fade_out_type,
        "actual_snr":         round(actual_snr, 2),
    }


# ════════════════════════════════════════════════════════════════
# 5. mix_voice_with_background
# ════════════════════════════════════════════════════════════════

def mix_voice_with_background(
    voice_file:        Path | str,
    background_file:   Path | str,
    output_file:       Path | str = Path("data/output/output_mix.wav"),
    voice_bg_ratio_db: float      = -20.0,
    fade_in_s:         float      = 2.0,
    fade_out_s:        float      = 2.0,
    fade_in_type:      FadeType   = "logarithmic",
    fade_out_type:     FadeType   = "exponential",
    start_time:       float      = 0.0,
    end_offset:       float      = 0.0,
) -> dict:
    """
    Mixe une piste voix avec un fond sonore continu.
    Applique des fondus longs (sigmoid par défaut) pour un rendu cinéma.

    Args:
        voice_file:        Fichier voix (référence de niveau)
        background_file:   Fichier musique/ambiance de fond
        output_file:       Fichier de sortie
        voice_bg_ratio_db: Écart dB voix/fond (-12 narration, -18 podcast, -10 léger)
        fade_in_s:         Durée fade in fond (défaut 2s)
        fade_out_s:        Durée fade out fond (défaut 2s)
        fade_in_type:      Courbe fade in  (défaut : logarithmic ⭐)
        fade_out_type:     Courbe fade out (défaut : exponential ⭐)
        start_time:       Timestamp (s) où le fond commence à se mélanger
        end_offset:       Durée (s) avant la fin de la voix où le fond commence à s'estomper

    Returns:
        {status, voice_file, background_file, output_file, sample_rate,
         voice_bg_ratio_db, rms_voice_db, rms_bg_before_db, rms_bg_after_db,
         gain_applied_db, duration_s}
    """
    logger.info("🎚️  Mixage voix + fond continu — ratio: %+.1f dB — %s",
                voice_bg_ratio_db, background_file)

    voice_path  = Path(voice_file)
    bg_path     = Path(background_file)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    y_voice, sr_voice = librosa.load(str(voice_path), sr=None)
    y_bg,    _        = librosa.load(str(bg_path),    sr=sr_voice)

    logger.info("📁 Voix : %s (%.1fs @ %dHz)", voice_path.name, len(y_voice)/sr_voice, sr_voice)
    logger.info("📁 Fond : %s (%.1fs)", bg_path.name, len(y_bg)/sr_voice)

    rms_voice     = float(np.mean(librosa.amplitude_to_db(librosa.feature.rms(y=y_voice)[0])))
    rms_bg        = float(np.mean(librosa.amplitude_to_db(librosa.feature.rms(y=y_bg)[0])))
    target_bg_db  = rms_voice + voice_bg_ratio_db
    gain_db       = target_bg_db - rms_bg
    y_bg_adjusted = y_bg * (10 ** (gain_db / 20))
    rms_bg_new    = float(np.mean(librosa.amplitude_to_db(librosa.feature.rms(y=y_bg_adjusted)[0])))

    logger.info("📊 RMS voix : %.2f dB  |  Cible fond : %.2f dB  |  Gain : %+.2f dB",
                rms_voice, target_bg_db, gain_db)

    voice_len = len(y_voice)

    # ✅ NOUVEAU — calcul de la zone active
    start_sample = int(start_time * sr_voice)
    end_sample   = voice_len - int(end_offset * sr_voice)
    active_len   = end_sample - start_sample

    if len(y_bg_adjusted) < active_len:
        repeats       = int(np.ceil(active_len / len(y_bg_adjusted)))
        y_bg_adjusted = np.tile(y_bg_adjusted, repeats)

    # Applique les fades uniquement sur le segment actif
    bg_segment = _apply_fade(
        y_bg_adjusted[:active_len], sr_voice,
        fade_in_s=fade_in_s, fade_out_s=fade_out_s,
        fade_in_type=fade_in_type, fade_out_type=fade_out_type
    )

    # Insère dans un buffer vide de la taille de la voix
    y_bg_final = np.zeros(voice_len)
    y_bg_final[start_sample:end_sample] = bg_segment

    logger.info("🎭 Fade in : %.2fs (%s)  |  Fade out : %.2fs (%s)",
                fade_in_s, fade_in_type, fade_out_s, fade_out_type)
    
    y_mix = y_voice + y_bg_final
    
    max_amp = float(np.max(np.abs(y_mix)))
    if max_amp > 1.0:
        logger.warning("⚠️  Saturation → normalisation (max: %.2f)", max_amp)
        y_mix = y_mix / max_amp

    sf.write(str(output_path), y_mix, sr_voice)
    logger.info("✓ Sauvegardé : %s (%.1fs)", output_path, len(y_mix)/sr_voice)

    return {
        "status":            "saved",
        "voice_file":        str(voice_path),
        "background_file":   str(bg_path),
        "output_file":       str(output_path),
        "sample_rate":       sr_voice,
        "voice_bg_ratio_db": voice_bg_ratio_db,
        "rms_voice_db":      round(rms_voice, 2),
        "rms_bg_before_db":  round(rms_bg, 2),
        "rms_bg_after_db":   round(rms_bg_new, 2),
        "gain_applied_db":   round(gain_db, 2),
        "fade_in_s":         fade_in_s,
        "fade_out_s":        fade_out_s,
        "fade_in_type":      fade_in_type,
        "fade_out_type":     fade_out_type,
        "start_time":        start_time,
        "end_offset":        end_offset,
        "duration_s":        round(len(y_mix) / sr_voice, 2),
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    sons   = find_background_sounds(keyword="forge")
    step_1 = mix_voice_with_noise(
        voice_file="data/audio/narration.wav",
        noise_file=sons["files"][0],
        output_file="data/audio/mix_step_1.wav",
        snr_db=15, start_time=5.0, noise_duration=4.0,
        fade_in_s=2.0, fade_out_s=2.0,
    )
    step_2 = mix_voice_with_noise(
        voice_file=step_1["output_file"],
        noise_file="data/audio/background_sounds/port/ambiance.wav",
        output_file="data/audio/mix_step_2.wav",
        snr_db=20, start_time=20.0, noise_duration=8.0,
        fade_in_s=2.0, fade_out_s=2.0,
    )
    mix_voice_with_background(
        voice_file=step_2["output_file"],
        background_file="data/audio/background_sounds/ambiance/mer.wav",
        output_file="data/audio/final_mix.wav",
        voice_bg_ratio_db=-26.0, fade_in_s=2.0, fade_out_s=2.0,
    )
