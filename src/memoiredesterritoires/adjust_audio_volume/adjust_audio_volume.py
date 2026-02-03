from pathlib import Path
import librosa
import soundfile as sf
import numpy as np

"""
═══════════════════════════════════════════════════════════════
Fonction d'ajustement du volume audio basée sur la perception
═══════════════════════════════════════════════════════════════
"""

def adjust_audio_volume(
    input_file: Path,
    output_file: Path | str = Path("data/generated_speech/output.wav"),
    volume_percent: float = 90
):
    """
    Ajuste le volume d'un fichier audio basé sur la perception humaine.
    
    Args:
        input_file: Fichier audio d'entrée
        output_file: Fichier audio de sortie
        volume_percent: Pourcentage du volume perçu (10 à 200)
                       - 100 = volume original (0 dB)
                       - 90 = 90% du volume perçu (-0.92 dB)
                       - 50 = moitié du volume perçu (-10 dB)
                       - 200 = double du volume perçu (+10 dB)
        
    Returns:
        Tuple (signal ajusté, sample rate)
        
    Example:
        >>> adjust_audio_volume(input_file, output_file, volume_percent=90)
        🔊 AJUSTEMENT DU VOLUME
        ════════════════════════════════════════════════════════════
        📊 RMS actuel: -26.38 dB
        🎚️  Volume cible: 90% du volume perçu
        📉 Réduction: -0.92 dB
        📊 RMS après ajustement: -27.30 dB
        ✓ Fichier sauvegardé: output.wav
    """
    
    print(f"\n🔊 AJUSTEMENT DU VOLUME")
    print("="*60)
    
    input_path = Path(input_file)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Charger l'audio
    y, sr = librosa.load(str(input_path), sr=None)
    
    # Analyser le niveau actuel
    rms_current = float(np.mean(librosa.amplitude_to_db(librosa.feature.rms(y=y)[0])))
    print(f"📊 RMS actuel: {rms_current:.2f} dB")
    
    # Conversion pourcentage perçu → décibels
    reduction_db = float(10 * np.log10(volume_percent / 100))
    
    print(f"🎚️  Volume cible: {volume_percent}% du volume perçu")
    if reduction_db < 0:
        print(f"📉 Réduction: {reduction_db:.2f} dB")
    elif reduction_db > 0:
        print(f"📈 Augmentation: +{reduction_db:.2f} dB")
    else:
        print(f"➡️  Aucun changement: 0 dB")
    
    # Appliquer la réduction
    gain = 10 ** (reduction_db / 20)  # Conversion dB vers amplitude
    y_adjusted = y * gain
    
    # Vérifier le nouveau niveau
    rms_new = float(np.mean(librosa.amplitude_to_db(librosa.feature.rms(y=y_adjusted)[0])))
    print(f"📊 RMS après ajustement: {rms_new:.2f} dB")
    print(f"   Différence réelle: {rms_new - rms_current:.2f} dB")
    
    # Vérification de clipping (saturation)
    max_amplitude = float(np.max(np.abs(y_adjusted)))
    if max_amplitude > 1.0:
        print(f"⚠️  ATTENTION: Saturation détectée! (max: {max_amplitude:.2f})")
        print(f"   Le son sera écrêté. Réduisez le volume_percent.")
    
    # Sauvegarder
    sf.write(str(output_path), y_adjusted, sr)
    print(f"✓ Fichier sauvegardé: {output_path}\n")
    
    return {
        "status": "saved",
        "input_file": str(input_path),
        "output_file": str(output_path),
        "sample_rate": sr,
        "volume_percent": volume_percent,
        "rms_before_db": round(rms_current, 2),
        "rms_after_db": round(rms_new, 2),
        "estimated_gain_db": round(reduction_db, 2),
        "max_amplitude": round(max_amplitude, 4),
    }

if __name__ == "__main__":
    # Exemple d'utilisation
    input_audio = Path("ElevenLabs_Jessica.mp3")
    output_audio = Path("output.wav")
    
    # Ajuster le volume à 90% du volume perçu
    adjust_audio_volume(input_audio, output_audio, volume_percent=90)


# print("📋 TABLE DE RÉFÉRENCE PERCEPTION ↔ DÉCIBELS")
# print("="*60)
# print("Volume perçu | Décibels | Description")
# print("-"*60)
# print("    10%      |  -10 dB  | Très faible (1/10 du volume)")
# print("    25%      |   -6 dB  | Quart du volume")
# print("    50%      |   -3 dB  | Moitié du volume")
# print("    70%      |  -1.5 dB | Légèrement réduit")
# print("    90%      |  -0.5 dB | Très légèrement réduit (DÉFAUT)")
# print("   100%      |   0 dB   | Volume original")
# print("   125%      |  +1.0 dB | Légèrement amplifié")
# print("   150%      |  +1.8 dB | 50% plus fort")
# print("   200%      |  +3.0 dB | Double du volume")
# print("="*60)
