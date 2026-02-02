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

