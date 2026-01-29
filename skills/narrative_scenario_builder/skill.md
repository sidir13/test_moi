# Narrative Scenario Builder

## Role

Construction de scénarios narratifs depuis une structure, adaptation du vocabulaire au public cible. Utilisé par Agent 2 pour générer le texte narratif.

Responsabilités :
- Construire le récit depuis la structure narrative
- Adapter le vocabulaire et la complexité au public
- Générer des moments clés dramatiques
- Créer des descriptions immersives
- Assurer fluidité et cohérence narrative

## Model Configuration

- Model: claude-opus-4-5
- Temperature: 0.8
- Max tokens: 6000

Raison : Température élevée pour créativité narrative, Opus pour qualité d'écriture.

## Functions

### build_scenario_from_structure

Construit un scénario complet depuis une structure narrative.

**Input** :
```json
{
  "structure": dict,  // Structure de Agent 1
  "config": dict,     // Configuration complète
  "historical_context": dict,  // Contexte enrichi
  "audio_transcriptions": list  // Transcriptions des archives disponibles
}
```

**Output** : Scénario narratif complet

**Usage** : Fonction principale d'Agent 2 pour générer le texte

**Comportement** :
- Pour chaque partie de la structure, génère le texte narratif
- Place les archives audio aux moments appropriés
- Crée les moments clés avec directions de ton
- Adapte le vocabulaire au public et à l'époque
- Assure transitions fluides entre parties

**Structure retournée** :
```json
{
  "partie_id": 1,
  "titre": "L'aube d'une journée ordinaire",
  "duree": 45.0,
  "texte_narration": "En ce matin de février 1905...",
  "ton": {
    "global": "contemplatif",
    "tempo_lecture": 110,
    "pauses": ["après 'brume'", "avant transition"],
    "intonation": "douce"
  },
  "moments_cles": [
    {
      "timestamp": "0:15",
      "action": "archive_audio",
      "fichier": "archive_temoignage_1.wav",
      "segment": {"start": 0, "end": 8},
      "fade_in": 1.0,
      "fade_out": 1.0,
      "volume": 0.7
    }
  ]
}
```

### adapt_vocabulary_to_audience

Adapte le vocabulaire d'un texte selon le public cible.

**Input** :
```json
{
  "text": str,
  "audience": str,  // "enfants", "grand_public", "specialiste", etc.
  "historical_authenticity": float  // 0.0-1.0
}
```

**Output** : Texte adapté

**Usage** : Post-traitement pour ajuster accessibilité

**Comportement** :
- **Pour enfants** : Simplifie phrases, remplace termes techniques
- **Pour grand public** : Équilibre entre authenticité et clarté
- **Pour spécialistes** : Préserve vocabulaire technique d'époque

**Exemple** :
```
Original (authentique) :
"Les portefaix manœuvraient les palans pour hisser les barriques de vin depuis la cale."

Adapté enfants :
"Les travailleurs du port utilisaient des cordes pour monter les gros tonneaux de vin depuis le bateau."

Adapté grand public :
"Les dockers actionnaient les palans (système de poulies) pour remonter les tonneaux de vin stockés dans la cale du navire."
```

### generate_dramatic_moment

Génère un moment clé dramatique ou émotionnel.

**Input** :
```json
{
  "context": str,
  "emotion_target": str,  // "tension", "émotion", "révélation", etc.
  "duration": float,
  "tone": str
}
```

**Output** : Description narrative du moment

**Usage** : Pour les points forts identifiés dans l'arc émotionnel

### create_immersive_description

Crée une description sensorielle immersive d'un lieu ou moment.

**Input** :
```json
{
  "subject": str,
  "senses": list,  // ["vue", "ouïe", "odorat", "toucher"]
  "mood": str,
  "period": int,
  "max_words": int
}
```

**Output** : Description immersive

**Usage** : Pour enrichir les passages d'exposition

## Notes

### Niveaux d'adaptation selon public

**Enfants (6-10 ans)** :
- Phrases courtes (< 15 mots)
- Vocabulaire simple
- Analogies concrètes
- Éviter abstractions

**Scolaire secondaire (11-17 ans)** :
- Phrases moyennes
- Quelques termes techniques expliqués
- Contexte historique accessible
- Stimulation intellectuelle

**Grand public** :
- Variété de structures
- Vocabulaire accessible avec enrichissements
- Équilibre narration/information
- Références culturelles communes

**Universitaire/Spécialiste** :
- Complexité assumée
- Vocabulaire technique préservé
- Références historiques précises
- Profondeur analytique

### Techniques narratives audio

**Show, don't tell** : Privilégier scènes concrètes aux explications abstraites

**Rythme audio** : Alterner passages rapides et lents, silences narratifs

**Ancrage sensoriel** : Descriptions visuelles, auditives, olfactives pour immersion

**Transitions sonores** : Utiliser les sons pour ponctuer les passages

**Répétition thématique** : Motifs narratifs qui créent cohérence
