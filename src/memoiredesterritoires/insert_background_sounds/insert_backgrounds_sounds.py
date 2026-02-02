from pathlib import Path
import librosa
import soundfile as sf
import numpy as np

"""
═══════════════════════════════════════════════════════════════
Fonction de mixage voix + bruit avec contrôle SNR
═══════════════════════════════════════════════════════════════
"""

def mix_voice_with_noise(
    voice_file: Path | str,
    noise_file: Path | str,
    output_file: Path | str = Path("data/generated_speech/mixed_output.wav"),
    snr_db: float = 15,
    start_time: float = 0,
    noise_duration: float | None = 3,
    noise_start_offset: float = 0
) -> dict:
    """
    Superpose un bruit sur une voix avec un contrôle précis du SNR.
    
    Args:
        voice_file: Fichier audio de la voix
        noise_file: Fichier audio du bruit (industriel, ambiance)
        output_file: Fichier de sortie
        snr_db: Rapport signal/bruit en dB (15 = voix 15dB plus forte que le bruit)
        start_time: Temps (en secondes) à partir duquel le bruit d'ambiance est intégré au scénario
        noise_duration: Durée du bruit (None = jusqu'à la fin de la voix)
        noise_start_offset: Début de lecture dans le fichier BRUIT (en secondes)
                           Utile pour éviter les silences au début du bruit
        
    Returns:
        Tuple (signal mixé, sample rate)
        
    Raises:
        FileNotFoundError: Si un fichier n'existe pas
        ValueError: Si l'offset du bruit est invalide
        
    Example:
        >>> mixed, sr = mix_voice_with_noise(
        ...     voice_file=Path("voice.mp3"),
        ...     noise_file=Path("industrial.wav"),
        ...     output_file=Path("mixed.wav"),
        ...     snr_db=20,
        ...     start_time=5.0,
        ...     noise_duration=10.0,
        ...     noise_start_offset=3.0
        ... )
    """
    
    print("="*60)
    print("🎙️ MIXAGE VOIX + BRUIT DE FOND")
    print("="*60)
    
    voice_path = Path(voice_file)
    noise_path = Path(noise_file)
    output_path = Path(output_file)
    
    # Vérification de l'existence des fichiers
    if not voice_path.exists():
        raise FileNotFoundError(f"Fichier voix introuvable: {voice_path}")
    if not noise_path.exists():
        raise FileNotFoundError(f"Fichier bruit introuvable: {noise_path}")
    
    # 1. CHARGER LES FICHIERS
    print("\n📂 Chargement des fichiers...")
    voice, sr_voice = librosa.load(str(voice_path), sr=None)
    noise, sr_noise = librosa.load(str(noise_path), sr=None)
    
    print(f"   Voix: {len(voice)/sr_voice:.2f}s @ {sr_voice}Hz")
    print(f"   Bruit: {len(noise)/sr_noise:.2f}s @ {sr_noise}Hz")
    
    # 2. RESAMPLER SI NÉCESSAIRE
    if sr_voice != sr_noise:
        print(f"\n⚙️ Resampling du bruit: {sr_noise}Hz → {sr_voice}Hz")
        noise = librosa.resample(noise, orig_sr=sr_noise, target_sr=sr_voice)
        sr_noise = sr_voice
    
    sr = sr_voice
    
    # 3. EXTRAIRE LA PARTIE DU BRUIT À PARTIR DE L'OFFSET
    noise_offset_sample = int(noise_start_offset * sr)
    
    if noise_offset_sample >= len(noise):
        raise ValueError(
            f"⚠️ Offset du bruit ({noise_start_offset}s) dépasse "
            f"la durée du fichier ({len(noise)/sr:.2f}s)"
        )
    
    if noise_offset_sample > 0:
        noise = noise[noise_offset_sample:]
        print(f"\n✂️ Bruit extrait à partir de {noise_start_offset:.2f}s")
        print(f"   Nouvelle durée disponible: {len(noise)/sr:.2f}s")
    
    # 4. CALCULER LES NIVEAUX RMS
    rms_voice = np.sqrt(np.mean(voice**2))
    rms_noise = np.sqrt(np.mean(noise**2))
    
    print(f"\n📊 Niveaux RMS originaux:")
    print(f"   Voix: {20*np.log10(rms_voice + 1e-10):.2f} dB")
    print(f"   Bruit: {20*np.log10(rms_noise + 1e-10):.2f} dB")
    
    # 5. AJUSTER LE NIVEAU DU BRUIT SELON LE SNR SOUHAITÉ
    # Formule: SNR = 20*log10(RMS_voix / RMS_bruit)
    # Donc: RMS_bruit_cible = RMS_voix / 10^(SNR/20)
    
    target_rms_noise = rms_voice / (10 ** (snr_db / 20))
    noise_gain = target_rms_noise / (rms_noise + 1e-10)
    noise_adjusted = noise * noise_gain
    
    print(f"\n🎚️ Ajustement du bruit pour SNR = {snr_db} dB:")
    print(f"   Gain appliqué au bruit: {20*np.log10(noise_gain):.2f} dB")
    print(f"   Nouveau niveau bruit: {20*np.log10(target_rms_noise):.2f} dB")
    
    # 6. PRÉPARER LE BRUIT À SUPERPOSER
    start_sample = int(start_time * sr)
    
    # Déterminer la durée du bruit
    if noise_duration is None:
        available_length = len(voice) - start_sample
    else:
        available_length = int(noise_duration * sr)
    
    # Gérer le cas où le bruit est plus court que nécessaire (boucler)
    if len(noise_adjusted) < available_length:
        print(f"\n🔁 Bruit trop court ({len(noise_adjusted)/sr:.2f}s), création d'une boucle...")
        repeats = int(np.ceil(available_length / len(noise_adjusted)))
        noise_adjusted = np.tile(noise_adjusted, repeats)
        print(f"   Répété {repeats} fois pour obtenir {len(noise_adjusted)/sr:.2f}s")
    
    # Couper le bruit à la longueur voulue
    noise_segment = noise_adjusted[:available_length]
    
    # 7. CRÉER LE SIGNAL MIXÉ
    mixed = voice.copy()
    
    # Ajouter le bruit à partir de start_sample
    end_sample = min(start_sample + len(noise_segment), len(mixed))
    actual_noise_length = end_sample - start_sample
    mixed[start_sample:end_sample] += noise_segment[:actual_noise_length]
    
    print(f"\n🔀 Mixage:")
    print(f"   Bruit source: {noise_start_offset:.2f}s → "
          f"{noise_start_offset + actual_noise_length/sr:.2f}s (fichier bruit)")
    print(f"   Position dans voix: {start_time:.2f}s → {(end_sample/sr):.2f}s")
    print(f"   Durée du bruit ajouté: {actual_noise_length/sr:.2f}s")
    
    # 8. NORMALISER SI NÉCESSAIRE (éviter la saturation)
    max_amplitude = np.max(np.abs(mixed))
    if max_amplitude > 0.99:
        print(f"\n⚠️ Saturation détectée ({max_amplitude:.3f}), normalisation appliquée")
        mixed = mixed / max_amplitude * 0.95
    
    # 9. VÉRIFIER LE SNR FINAL
    voice_segment = voice[start_sample:end_sample]
    rms_voice_seg = np.sqrt(np.mean(voice_segment**2))
    rms_noise_seg = np.sqrt(np.mean(noise_segment[:actual_noise_length]**2))
    actual_snr = 20 * np.log10(rms_voice_seg / (rms_noise_seg + 1e-10))
    
    print(f"\n✓ SNR final mesuré: {actual_snr:.2f} dB")
    
    if actual_snr >= 20:
        print("   → Excellente intelligibilité (voix très claire)")
    elif actual_snr >= 10:
        print("   → Bonne intelligibilité (léger bruit de fond)")
    elif actual_snr >= 0:
        print("   → Intelligibilité acceptable (bruit perceptible)")
    else:
        print("   → ⚠️ Intelligibilité difficile (bruit fort)")
    
    # 10. SAUVEGARDER
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), mixed, sr)
    print(f"\n💾 Fichier sauvegardé: {output_path}")
    print("="*60)
    
    return {
        "status": "mixed",
        "voice_file": str(voice_path),
        "noise_file": str(noise_path),
        "output_file": str(output_path),
        "sample_rate": sr,
        "snr_db": snr_db,
        "start_time": start_time,
        "noise_duration": noise_duration,
        "noise_start_offset": noise_start_offset,
        "actual_snr": round(actual_snr, 2),
    }

print("✓ Fonction de mixage chargée")
