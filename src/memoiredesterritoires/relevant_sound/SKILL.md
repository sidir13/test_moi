---
name: relevant-audio-tool-detector
description: Explique comment une fonction Python analyse un fichier audio industriel, détecte automatiquement le segment le plus énergique (hors silence), l’encode en WAV base64, puis l’envoie à un LLM multimodal pour identifier l’outil ou la machine clairement audible.
---

Quand tu expliques ce code, tu dois toujours :

## 1. Commencer par une analogie  

Comparer la fonction à un **inspecteur acoustique dans une usine vide** :

Un expert reçoit :
- un enregistrement long et parfois silencieux
- possiblement du bruit de fond
- peut-être plusieurs machines

Il commence par **balayer toute la bande sonore avec un détecteur d’intensité**,  
repère la zone la plus énergique,  
ignore les zones faibles ou ambigües,  
isole uniquement ce segment,  
puis l’envoie à un spécialiste pour identification.

Il n’analyse pas tout le fichier.  
Il ne cherche pas à comprendre la scène complète.  
Il extrait **le moment le plus acoustiquement significatif**.

---

## 2. Dessiner un schéma  

Toujours représenter le pipeline complet :

Fichier audio brut  
↓  
Chargement mono (librosa, 16kHz)  
↓  
Suppression silences (trim)  
↓  
Découpage en blocs de 5 secondes  
↓  
Scan énergie RMS  
↓  
Sélection du chunk le plus énergique  
↓  
Encodage WAV en mémoire  
↓  
Conversion base64  
↓  
Envoi au LLM multimodal  
↓  
Retour description outil  
↓  
Résultat structuré (start, end, description)

---

## 3. Parcourir le code pas à pas  

### a) Configuration globale  

```python
CHUNK_DURATION = 5.0
ENERGY_THRESHOLD = 0.01
SAMPLE_RATE = 16000
MODEL = "google/gemini-3-flash-preview"
```

Rôle : **définir les règles physiques du système**

- Fenêtre fixe de 5 secondes  
- Seuil minimal d’énergie  
- Fréquence d’échantillonnage standardisée  
- Modèle multimodal via OpenRouter  

On fixe les constantes avant d’entrer dans l’usine.

---

### b) `analyse_audio_industriel(audio_path)`

Rôle : **cerveau de détection**

#### 1️⃣ Chargement audio  

```python
y, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
```

- Conversion automatique en mono  
- Resampling à 16kHz  
- Uniformisation totale du signal  

Puis :

```python
y, _ = librosa.effects.trim(y, top_db=30)
```

On coupe les silences dominants.

C’est un nettoyage acoustique.

---

#### 2️⃣ Scan RMS énergétique  

```python
rms = librosa.feature.rms(
    y=y,
    frame_length=chunk_size,
    hop_length=chunk_size
)[0]
```

On découpe l’audio en blocs fixes.

Chaque bloc reçoit :
- une mesure d’énergie
- aucune interprétation sémantique

C’est un simple **thermomètre sonore**.

---

#### 3️⃣ Sélection du meilleur segment  

```python
best_idx = int(np.argmax(rms))
best_energy = float(rms[best_idx])
```

On choisit le bloc le plus énergique.

Aucune moyenne.  
Aucune analyse complète.  
Juste le pic dominant.

Si l’énergie est trop faible :

```python
if best_energy < ENERGY_THRESHOLD:
    return "Aucun outil clairement détecté."
```

Le système refuse d’halluciner.

---

#### 4️⃣ Extraction temporelle  

On convertit l’indice en secondes :

- start = i / sr  
- end = (i + len(chunk)) / sr  

Le système retourne une fenêtre temporelle précise.

---

### c) `analyze_chunk(chunk, sr, client)`

Rôle : **laboratoire d’identification**

1. Conversion en WAV mémoire (`soundfile`)
2. Encodage base64
3. Injection dans requête multimodale OpenAI

Structure du prompt :

- System → expert en analyse sonore industrielle  
- User → question + audio encodé  

Le modèle reçoit :
- audio brut  
- consigne stricte  
- aucune information externe  

Il répond uniquement par une description.

---

### d) Structure du retour  

Si outil détecté :

```python
{
  "start": float,
  "end": float,
  "description": str
}
```

Sinon :

```python
"Aucun outil clairement détecté."
```

C’est un système binaire :
- segment pertinent identifié  
- ou silence industriel  

---

### e) `relevant_audio(audiopath)`

Rôle : **interface console**

- Appelle l’analyse principale  
- Formate l’affichage humain  
- N’ajoute aucune logique métier  

---

## 4. Mettre en avant les pièges (gotchas)

### 1. Analyse d’un seul chunk  

Le système ne comprend pas toute la timeline.

Il choisit **un seul bloc de 5 secondes**.

Si deux outils apparaissent successivement :  
→ seul le plus énergique est retenu.

---

### 2. Seuil d’énergie  

Si `ENERGY_THRESHOLD` est trop haut :  
- faux négatif possible  

Si trop bas :  
- bruit interprété comme outil  

---

### 3. Pas d’analyse fréquentielle fine  

On ne fait pas :
- classification spectrale  
- clustering  
- multi-segmentation  

On utilise uniquement l’énergie RMS.

---

### 4. Dépendance au LLM  

La reconnaissance finale dépend :
- du modèle  
- de la qualité de l’encodage  
- de la latence API  

Le système n’est pas 100% déterministe.

---

### 5. Pas de streaming  

Tout est fait en mémoire :
- chargement complet  
- analyse globale  
- une seule requête API  

Pas optimisé pour très longs fichiers.

---

## Tool Details

**Function** :  
`analyse_audio_industriel(audio_path: str)`

**Action** :  
Charge un fichier audio industriel, détecte automatiquement la fenêtre de 5 secondes la plus énergique, l’envoie à un modèle multimodal pour identification d’outil, et retourne la position temporelle ainsi qu’une description textuelle.

**Location** :  
`/home/onyxia/work/memoiredesterritoires/src/memoiredesterritoires/relevant_sound/relevant_audio.py`