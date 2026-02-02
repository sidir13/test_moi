from pathlib import Path
import librosa
import soundfile as sf
import numpy as np
import warnings


# Configuration des chemins
DATA_DIR = Path.cwd().parent.parent.parent / "data"
AUDIO_INDUSTRIAL_DIR = DATA_DIR / "audio" / "background_sounds" / "pont_roulant"
AUDIO_VOICE_DIR = DATA_DIR / "Speech Final"
OUTPUT_DIR = DATA_DIR / "discours"
NOISE_DIR = DATA_DIR / "audio" / "background_sounds"  # Adapter selon votre structure

# Créer les dossiers de sortie s'ils n'existent pas
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Vérification
print("✓ Configuration chargée")
print(f"  Répertoire data: {DATA_DIR}")
print(f"  Dossier sortie: {OUTPUT_DIR}")
print(f"  Exists: {DATA_DIR.exists()}")

# Cellule 3 : Fonction d'analyse audio complète
"""
═══════════════════════════════════════════════════════════════
Fonction principale d'analyse audio
═══════════════════════════════════════════════════════════════
"""

def analyze_audio_file(audio_file: Path, verbose: bool = True) -> dict:
    """
    Analyse complète d'un fichier audio avec extraction de features.
    
    Args:
        audio_file: Chemin vers le fichier audio
        verbose: Si True, affiche les résultats détaillés
        
    Returns:
        Dictionnaire contenant toutes les features extraites
        
    Raises:
        FileNotFoundError: Si le fichier n'existe pas
        ValueError: Si le fichier ne peut pas être chargé
    """
    """
    ═══════════════════════════════════════════════════════════════
    Fonctions d'interprétation des caractéristiques audio
    ═══════════════════════════════════════════════════════════════
    """

    def interpret_rms(rms_db_mean: float) -> str:
        """
        Interprète le niveau RMS (Root Mean Square) en dB.
        
        Args:
            rms_db_mean: Niveau RMS moyen en décibels
            
        Returns:
            Description textuelle du niveau sonore
        """
        if rms_db_mean > -10:
            return "→ Son TRÈS FORT (proche de la saturation)"
        elif rms_db_mean > -20:
            return "→ Son FORT (niveau élevé)"
        elif rms_db_mean > -30:
            return "→ Son MODÉRÉ (niveau moyen)"
        elif rms_db_mean > -40:
            return "→ Son FAIBLE (niveau bas)"
        else:
            return "→ Son TRÈS FAIBLE (quasi-silence)"


    def interpret_f0(f0_mean: float) -> str:
        """
        Interprète la fréquence fondamentale (F0).
        
        Args:
            f0_mean: Fréquence fondamentale moyenne en Hz
            
        Returns:
            Description de la hauteur tonale
        """
        if f0_mean < 100:
            note = "grave (< Do2)"
        elif f0_mean < 200:
            note = "médium-grave (Do2-Sol2)"
        elif f0_mean < 400:
            note = "médium (Sol2-Sol3)"
        elif f0_mean < 800:
            note = "médium-aigu (Sol3-Sol4)"
        else:
            note = "aigu (> Sol4)"
        return f"→ Fréquence de base {note} - vibration à {f0_mean:.0f} Hz"


    def interpret_centroid(centroid_mean: float) -> str:
        """
        Interprète le centroïde spectral (brillance du son).
        
        Args:
            centroid_mean: Centroïde spectral moyen en Hz
            
        Returns:
            Description de la brillance perceptuelle
        """
        if centroid_mean < 1000:
            return "→ Son SOMBRE/MAT (peu brillant, dominé par les basses)"
        elif centroid_mean < 2000:
            return "→ Son PEU BRILLANT (fréquences moyennes dominantes)"
        elif centroid_mean < 3000:
            return "→ Son MOYENNEMENT BRILLANT (équilibré)"
        elif centroid_mean < 5000:
            return "→ Son BRILLANT (présence d'aigus marquée)"
        else:
            return "→ Son TRÈS BRILLANT (dominé par les hautes fréquences)"


    def interpret_rolloff(rolloff_mean: float) -> str:
        """
        Interprète le rolloff spectral (85% de l'énergie).
        
        Args:
            rolloff_mean: Fréquence de rolloff moyenne en Hz
            
        Returns:
            Description de la distribution spectrale
        """
        if rolloff_mean < 2000:
            return "→ Contenu principalement BASSES FRÉQUENCES"
        elif rolloff_mean < 4000:
            return "→ Contenu jusqu'aux FRÉQUENCES MOYENNES"
        elif rolloff_mean < 8000:
            return "→ Présence de HAUTES FRÉQUENCES modérée"
        else:
            return "→ Riche en TRÈS HAUTES FRÉQUENCES"


    def interpret_bandwidth(bandwidth_mean: float) -> str:
        """
        Interprète la bande passante spectrale (richesse harmonique).
        
        Args:
            bandwidth_mean: Bande passante moyenne en Hz
            
        Returns:
            Description de la complexité spectrale
        """
        if bandwidth_mean < 1000:
            return "→ Son PUR/TONAL (peu de composantes fréquentielles)"
        elif bandwidth_mean < 2500:
            return "→ Son MOYENNEMENT RICHE (quelques harmoniques)"
        elif bandwidth_mean < 4000:
            return "→ Son RICHE (spectre complexe avec harmoniques)"
        else:
            return "→ Son TRÈS COMPLEXE/BRUITÉ (large spectre fréquentiel)"


    def interpret_zcr(zcr_mean: float) -> str:
        """
        Interprète le zero crossing rate (contenu haute fréquence).
        
        Args:
            zcr_mean: Taux de passage par zéro moyen
            
        Returns:
            Description du contenu fréquentiel
        """
        if zcr_mean < 0.05:
            return "→ Dominance BASSES FRÉQUENCES (son grave)"
        elif zcr_mean < 0.15:
            return "→ Contenu fréquentiel ÉQUILIBRÉ"
        else:
            return "→ Dominance HAUTES FRÉQUENCES (son aigu/bruité)"


    def interpret_mfccs(mfccs_shape: tuple) -> str:
        """
        Interprète la forme des MFCCs (Mel-Frequency Cepstral Coefficients).
        
        Args:
            mfccs_shape: Tuple (n_coefficients, n_frames)
            
        Returns:
            Description de la représentation MFCC
        """
        n_coef, n_frames = mfccs_shape
        duration_analysis = n_frames * 0.023  # ~23ms par frame en moyenne
        return f"→ {n_coef} coefficients sur {n_frames} fenêtres temporelles (~{duration_analysis:.1f}s)"

    # Vérification de l'existence du fichier
    if not audio_file.exists():
        raise FileNotFoundError(f"Fichier introuvable: {audio_file}")
    
    if verbose:
        print("="*60)
        print("ANALYSE AUDIO DÉTAILLÉE")
        print("="*60)
        print(f"\n📁 Fichier: {audio_file.name}\n")
    
    # Chargement du fichier
    y, sr = librosa.load(str(audio_file), sr=None)
    
    # ==== INFORMATIONS TEMPORELLES ====
    duration = librosa.get_duration(y=y, sr=sr)
    
    if verbose:
        print("━"*60)
        print("📊 INFORMATIONS TEMPORELLES")
        print("━"*60)
        print(f"Durée: {duration:.2f} secondes")
        print(f"Taux d'échantillonnage: {sr} Hz")
        
        if sr == 44100:
            print("   → Standard CD audio (qualité professionnelle)")
        elif sr == 48000:
            print("   → Standard production audio/vidéo")
        elif sr == 16000:
            print("   → Qualité téléphonie/reconnaissance vocale")
        
        print(f"Nombre d'échantillons: {len(y):,}")
    
    # ==== INTENSITÉ ====
    rms = librosa.feature.rms(y=y)[0]
    rms_db = librosa.amplitude_to_db(rms)
    rms_mean = np.mean(rms_db)
    rms_std = np.std(rms_db)
    
    if verbose:
        print("\n" + "━"*60)
        print("🔊 INTENSITÉ SONORE")
        print("━"*60)
        print(f"Intensité RMS moyenne: {rms_mean:.2f} dB")
        print(f"   {interpret_rms(rms_mean)}")
        print(f"Écart-type RMS: {rms_std:.2f} dB")
        
        if rms_std > 10:
            print(f"   → Dynamique IMPORTANTE (grandes variations d'intensité)")
        elif rms_std > 5:
            print(f"   → Dynamique MODÉRÉE")
        else:
            print(f"   → Dynamique FAIBLE (son stable)")
    
    # ==== FRÉQUENCES ====
    f0 = librosa.yin(y, fmin=50, fmax=400)
    spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    zero_crossing_rate = librosa.feature.zero_crossing_rate(y)[0]
    
    centroid_mean = np.mean(spectral_centroids)
    rolloff_mean = np.mean(spectral_rolloff)
    bandwidth_mean = np.mean(spectral_bandwidth)
    zcr_mean = np.mean(zero_crossing_rate)
    
    if verbose:
        print("\n" + "━"*60)
        print("🎵 ANALYSE FRÉQUENTIELLE")
        print("━"*60)
        
        if np.any(f0 > 0):
            f0_mean = np.mean(f0[f0>0])
            print(f"F0 moyenne (fréquence fondamentale): {f0_mean:.2f} Hz")
            print(f"   {interpret_f0(f0_mean)}")
        else:
            print("F0: Non détectable (pas de fondamentale claire)")
            f0_mean = None
        
        print(f"\nCentroïde spectral moyen: {centroid_mean:.2f} Hz")
        print(f"   {interpret_centroid(centroid_mean)}")
        print(f"   💡 Le centroïde mesure la BRILLANCE perçue du son")
        
        print(f"\nRolloff spectral moyen: {rolloff_mean:.2f} Hz")
        print(f"   {interpret_rolloff(rolloff_mean)}")
        print(f"   💡 85% de l'énergie est sous {rolloff_mean:.0f} Hz")
        
        print(f"\nBande passante moyenne: {bandwidth_mean:.2f} Hz")
        print(f"   {interpret_bandwidth(bandwidth_mean)}")
        print(f"   💡 Mesure la richesse/complexité harmonique")
        
        print(f"\nZero crossing rate moyen: {zcr_mean:.4f}")
        print(f"   {interpret_zcr(zcr_mean)}")
        print(f"   💡 Indique le contenu en hautes fréquences")
    
    # ==== MFCCs ====
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    
    if verbose:
        print("\n" + "━"*60)
        print("🔬 REPRÉSENTATION AVANCÉE")
        print("━"*60)
        print(f"MFCCs shape: {mfccs.shape}")
        print(f"   {interpret_mfccs(mfccs.shape)}")
        print(f"   💡 'Empreinte digitale' du timbre pour classification")
    
    # ==== RÉSUMÉ ====
    if verbose:
        print("\n" + "="*60)
        print("📋 RÉSUMÉ INTERPRÉTATIF")
        print("="*60)
        print(f"\nCe fichier audio de {duration:.0f}s est un son:")
        
        if rms_mean > -20:
            print("  • FORT en intensité")
        elif rms_mean > -30:
            print("  • MODÉRÉ en intensité")
        else:
            print("  • FAIBLE en intensité")
        
        if centroid_mean < 2000:
            print(f"  • PEU BRILLANT (sombre)")
        elif centroid_mean < 4000:
            print(f"  • MOYENNEMENT BRILLANT")
        else:
            print(f"  • TRÈS BRILLANT (clair)")
        
        if bandwidth_mean > 3000:
            print(f"  • RICHE en harmoniques (spectre complexe)")
        else:
            print(f"  • Spectre relativement simple")
        
        if zcr_mean < 0.05:
            print(f"  • Dominé par les BASSES FRÉQUENCES")
        elif zcr_mean > 0.15:
            print(f"  • Dominé par les HAUTES FRÉQUENCES")
        else:
            print(f"  • Équilibré fréquentiellement")
        
        print("\n" + "="*60)
    
    # Retourner un dictionnaire avec toutes les features
    return {
        'filename': audio_file.name,
        'duration': duration,
        'sample_rate': sr,
        'n_samples': len(y),
        'rms_mean_db': rms_mean,
        'rms_std_db': rms_std,
        'f0_mean': f0_mean if np.any(f0 > 0) else None,
        'spectral_centroid_mean': centroid_mean,
        'spectral_rolloff_mean': rolloff_mean,
        'spectral_bandwidth_mean': bandwidth_mean,
        'zero_crossing_rate_mean': zcr_mean,
        'mfccs_shape': mfccs.shape,
        'signal': y,
        'sr': sr
    }


print("✓ Fonction d'analyse chargée")


# Cellule 5 : Fonction de réduction de volume
"""
═══════════════════════════════════════════════════════════════
Fonction d'ajustement du volume audio
═══════════════════════════════════════════════════════════════
"""

def adjust_audio_volume(input_file: Path, output_file: Path, reduction_db: float = -10):
    """
    Ajuste le volume d'un fichier audio.
    
    Args:
        input_file: Fichier audio d'entrée
        output_file: Fichier audio de sortie
        reduction_db: Réduction en dB (négatif pour baisser, positif pour augmenter)
        
    Returns:
        Tuple (signal ajusté, sample rate)
        
    Example:
        >>> adjust_audio_volume(input_file, output_file, reduction_db=-10)
        RMS actuel: -26.38 dB
        RMS après réduction: -36.38 dB
        ✓ Fichier sauvegardé: output.wav
    """
    
    print(f"\n🔊 AJUSTEMENT DU VOLUME")
    print("="*60)
    
    # Charger l'audio
    y, sr = librosa.load(str(input_file), sr=None)
    
    # Analyser le niveau actuel
    rms_current = np.mean(librosa.amplitude_to_db(librosa.feature.rms(y=y)[0]))
    print(f"📊 RMS actuel: {rms_current:.2f} dB")
    
    # Appliquer la réduction
    gain = 10 ** (reduction_db / 20)  # Conversion dB vers amplitude
    y_adjusted = y * gain
    
    # Vérifier le nouveau niveau
    rms_new = np.mean(librosa.amplitude_to_db(librosa.feature.rms(y=y_adjusted)[0]))
    print(f"📊 RMS après ajustement: {rms_new:.2f} dB")
    print(f"   Différence appliquée: {rms_new - rms_current:.2f} dB")
    
    # Sauvegarder
    sf.write(str(output_file), y_adjusted, sr)
    print(f"✓ Fichier sauvegardé: {output_file}\n")
    
    return y_adjusted, sr


print("✓ Fonction d'ajustement de volume chargée")


# Cellule 7 : Fonction de mixage voix + bruit
"""
═══════════════════════════════════════════════════════════════
Fonction de mixage voix + bruit avec contrôle SNR
═══════════════════════════════════════════════════════════════
"""

def mix_voice_with_noise(
    voice_file: Path,
    noise_file: Path,
    output_file: Path,
    snr_db: float = 15,
    start_time: float = 0,
    noise_duration: float = None,
    noise_start_offset: float = 0
) -> tuple:
    """
    Superpose un bruit sur une voix avec un contrôle précis du SNR.
    
    Args:
        voice_file: Fichier audio de la voix
        noise_file: Fichier audio du bruit (industriel, ambiance)
        output_file: Fichier de sortie
        snr_db: Rapport signal/bruit en dB (15 = voix 15dB plus forte que le bruit)
        start_time: Moment où le bruit commence dans la VOIX (en secondes)
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
    
    # Vérification de l'existence des fichiers
    if not voice_file.exists():
        raise FileNotFoundError(f"Fichier voix introuvable: {voice_file}")
    if not noise_file.exists():
        raise FileNotFoundError(f"Fichier bruit introuvable: {noise_file}")
    
    # 1. CHARGER LES FICHIERS
    print("\n📂 Chargement des fichiers...")
    voice, sr_voice = librosa.load(str(voice_file), sr=None)
    noise, sr_noise = librosa.load(str(noise_file), sr=None)
    
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
    output_file.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_file), mixed, sr)
    print(f"\n💾 Fichier sauvegardé: {output_file}")
    print("="*60)
    
    return mixed, sr

    # # Exemple de mixage
    # """
    # Exemple : Mixer une voix avec un bruit industriel
    # """

    # # Configuration du mixage
    # CONFIG = {
    #     'voice_file': AUDIO_VOICE_DIR / "ElevenLabs_Spuds_Oxley.mp3",
    #     'noise_file': AUDIO_INDUSTRIAL_DIR / "AV-1-S-OUT-401.wav",
    #     'output_file': OUTPUT_DIR / "mixage_SNR20.wav",
    #     'snr_db': 20,  # Voix 20 dB plus forte que le bruit
    #     'start_time': 5.0,  # Le bruit apparaît à 5s de la voix
    #     'noise_duration': 5.0,  # Le bruit dure 5 secondes
    #     'noise_start_offset': 5.0  # Commence à lire le bruit à 5s (évite le silence)
    # }

    # # Lancer le mixage
    # mixed, sr = mix_voice_with_noise(**CONFIG)

    # print(f"\n🎉 Mixage terminé ! Le fichier est disponible dans : {CONFIG['output_file']}")


print("✓ Fonction de mixage chargée")
