# Ambiance Sound Selector

## Role

Sélection intelligente des sons d'ambiance depuis la bibliothèque sonore. Utilisé par Agent 3 pour choisir les sons optimaux selon critères multiples.

Responsabilités :
- Rechercher dans la bibliothèque sonore par tags et filtres
- Calculer score de pertinence selon critères multiples
- Sélectionner le son optimal ou proposer alternatives
- Gérer fallbacks si son non trouvé
- Extraire métadonnées des fichiers audio

## Model Configuration

- Model: claude-sonnet-4-5
- Temperature: 0.3
- Max tokens: 2000

Raison : Température basse pour sélection précise et cohérente.

## Python Tools

Enabled: true

Utilisé pour :
- Lecture du fichier index de la bibliothèque sonore
- Calculs de scoring
- Extraction de métadonnées audio (durée, sample rate)

## Functions

### search_sound_library

Recherche sons par tags et filtres dans la bibliothèque.

**Input** :
```json
{
  "tags": list,  // Tags requis (ex: ["port", "ambiance", "morning"])
  "filters": {
    "period": str,  // optionnel: "1900s", "1950s"
    "mood": str,  // optionnel: "calm", "tense", "busy"
    "min_duration": float,  // optionnel: durée minimum en secondes
    "quality": str  // optionnel: "high", "medium", "low", "vintage"
  },
  "library_path": str
}
```

**Output** : Liste de sons candidats avec métadonnées

**Usage** : Recherche initiale pour trouver candidats

**Comportement** :
- Charge l'index de la bibliothèque sonore (JSON)
- Filtre par tags (intersection)
- Applique filtres additionnels
- Retourne liste triée par pertinence

**Structure retournée** :
```json
{
  "candidates": [
    {
      "file": "port_ambiance_morning_1905.wav",
      "tags": ["port", "ambiance", "morning", "1900s"],
      "duration": 120.5,
      "metadata": {
        "period": "1900s",
        "mood": "calm",
        "quality": "vintage",
        "description": "Ambiance portuaire matinale avec cloches"
      }
    }
  ],
  "total_found": 5
}
```

### calculate_sound_relevance

Calcule score de pertinence d'un son selon critères.

**Input** :
```json
{
  "sound": dict,  // Son candidat
  "criteria": {
    "required_tags": list,
    "mood": str,
    "period": str,
    "duration_target": float,
    "weights": {  // optionnel
      "tags": 0.4,
      "mood": 0.3,
      "period": 0.2,
      "duration": 0.1
    }
  }
}
```

**Output** :
```json
{
  "relevance_score": 0.85,  // 0.0-1.0
  "breakdown": {
    "tags_score": 0.9,
    "mood_score": 0.8,
    "period_score": 1.0,
    "duration_score": 0.7
  },
  "reasoning": "Excellent match pour tags et période, mood compatible"
}
```

**Usage** : Scoring de chaque candidat pour sélection finale

**Formule** :
```
relevance_score = (
  tags_score * weight_tags +
  mood_score * weight_mood +
  period_score * weight_period +
  duration_score * weight_duration
)
```

**Calcul par critère** :
- **tags_score** : (tags matched / tags required)
- **mood_score** : 1.0 si exact, 0.7 si compatible, 0.3 si différent
- **period_score** : 1.0 si période exacte, 0.8 si proche, 0.5 si générique
- **duration_score** : 1.0 si durée >= target, sinon (duration / target)

### select_optimal_sound

Sélectionne le son optimal depuis une liste de candidats.

**Input** :
```json
{
  "candidates": list,
  "criteria": dict,
  "return_alternatives": bool  // optionnel, default false
}
```

**Output** :
```json
{
  "selected": {
    "file": "port_ambiance_morning_1905.wav",
    "relevance_score": 0.92
  },
  "alternatives": [...]  // si return_alternatives=true
}
```

**Usage** : Sélection finale après scoring

### get_sound_metadata

Extrait métadonnées complètes d'un fichier audio.

**Input** :
```json
{
  "file_path": str
}
```

**Output** :
```json
{
  "duration": 120.5,
  "sample_rate": 48000,
  "channels": 2,
  "format": "WAV",
  "bit_depth": 24,
  "file_size": 25600000
}
```

**Usage** : Validation technique des sons sélectionnés

## Notes

### Structure de la bibliothèque sonore

```
data/sound_library/
├── index.json  // Index principal avec métadonnées
├── ambiances/
│   ├── port/
│   │   ├── port_ambiance_morning_1905.wav
│   │   └── port_ambiance_busy_1920.wav
│   └── factory/
├── archives/
│   ├── testimonies/
│   └── speeches/
├── sfx/
│   ├── tools/
│   └── transport/
└── music/
    └── motifs/
```

**index.json structure** :
```json
{
  "sounds": [
    {
      "file": "ambiances/port/port_ambiance_morning_1905.wav",
      "tags": ["port", "ambiance", "morning", "1900s", "calm"],
      "duration": 120.5,
      "metadata": {
        "period": "1900s",
        "mood": "calm",
        "quality": "vintage",
        "description": "...",
        "source": "Archives sonores"
      }
    }
  ]
}
```

### Mood compatibility matrix

| Demandé | Compatible |
|---------|-----------|
| calm | peaceful, quiet, serene |
| tense | anxious, worried, uneasy |
| busy | active, crowded, energetic |
| dramatic | intense, powerful, emotional |
| contemplative | calm, peaceful, reflective |

### Fallback strategies

Si aucun son ne match :
1. Élargir la recherche (retirer tags optionnels)
2. Accepter période proche
3. Utiliser son générique de la catégorie
4. Suggérer création/enregistrement
5. En dernier recours : silence ou son générique
