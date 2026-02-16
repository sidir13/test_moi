# Narrative Scenario Builder

## Role

Construction de scénarios narratifs depuis une structure, adaptation du vocabulaire au public cible. Utilisé par Agent 2 comme **fallback** quand la génération directe échoue.

Responsabilités :
- Construire le récit depuis la structure narrative, partie par partie
- Adapter le vocabulaire et la complexité au public
- Générer des moments clés dramatiques
- Créer des descriptions immersives
- Assurer fluidité et cohérence narrative
- Intégrer les transcriptions audio comme source primaire
- Respecter l'angle de scénarisation et le prompt utilisateur

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
  "structure": dict,
  "config": dict,
  "historical_context": dict,
  "audio_transcriptions": list
}
```

**Output** : Liste de parties de scénario narratif

**Usage** : Fallback d'Agent 2 pour générer le texte partie par partie

**Comportement** :
- Pour chaque partie de la structure, génère le texte narratif via un appel LLM dédié
- Place les archives audio aux moments appropriés
- Crée les moments clés avec directions de ton
- Adapte le vocabulaire au public et à l'époque
- Intègre les transcriptions audio fournies dans le prompt
- Assure transitions fluides entre parties

**Garde-fous anti-hallucination** :
- Le prompt contient un bloc explicite interdisant l'invention de faits historiques
- Seuls le contexte historique et les transcriptions sont autorisés comme sources de faits
- Les atmosphères et émotions peuvent être librement créées

### adapt_vocabulary_to_audience

Adapte le vocabulaire d'un texte selon le public cible.

**Input** :
```json
{
  "text": str,
  "audience": str,
  "historical_authenticity": float
}
```

**Output** : Texte adapté

**Usage** : Post-traitement pour ajuster accessibilité

### generate_dramatic_moment

Génère un moment clé dramatique ou émotionnel.

**Input** :
```json
{
  "context": str,
  "emotion_target": str,
  "duration": float,
  "tone": str
}
```

**Output** : Description narrative du moment

### create_immersive_description

Crée une description sensorielle immersive d'un lieu ou moment.

**Input** :
```json
{
  "subject": str,
  "senses": list,
  "mood": str,
  "period": int,
  "max_words": int
}
```

**Output** : Description immersive

## Notes

### Différence avec la génération directe d'Agent 2

Agent 2 préfère générer **toutes les parties en une seule requête LLM** pour assurer la cohérence globale. Ce skill est le **fallback** : il génère partie par partie, ce qui peut entraîner des répétitions entre sections.

### Techniques narratives audio

- **Show, don't tell** : Privilégier scènes concrètes aux explications abstraites
- **Rythme audio** : Alterner passages rapides et lents, silences narratifs
- **Ancrage sensoriel** : Descriptions visuelles, auditives, olfactives pour immersion
- **Transitions sonores** : Utiliser les sons pour ponctuer les passages
- **Répétition thématique** : Motifs narratifs qui créent cohérence
