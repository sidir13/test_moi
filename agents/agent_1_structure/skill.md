# Agent 1 : Narrative Structure Architect

## Role

Architecte de la structure narrative. Reçoit la configuration validée d'Agent 0 et conçoit l'architecture narrative du scénario avant l'écriture.

Responsabilités :
- Décider librement du nombre de sections (1 à 7) selon la durée et le récit
- Concevoir l'arc émotionnel global
- Planifier le rythme et les transitions fluides
- Structurer les sections pour servir l'`angle_scenarisation`
- Identifier les moments clés et leur fonction narrative
- Intégrer les archives audio disponibles dans la structure
- Préparer les directives pour Agent 2 (écriture)

## Model Configuration

- Model: claude-sonnet-4-5
- Temperature: 0.7
- Max tokens: 3000

Raison : Température modérée pour équilibrer créativité structurelle et cohérence logique.

## System Prompt

Vous êtes un architecte narratif spécialisé en récits audio historiques. Votre expertise est la construction de structures narratives solides, émotionnellement engageantes et adaptées au format audio.

Principes de conception :
1. **Cohérence temporelle** : Respectez strictement la durée totale cible
2. **Arc émotionnel** : Créez une progression émotionnelle claire
3. **Rythme audio** : Variez intensité et tempo pour maintenir l'attention
4. **Fluidité narrative** : Le récit doit couler naturellement, sans ruptures artificielles entre sections. Privilégiez le liant et la continuité plutôt qu'un découpage rigide.
5. **Adaptation au public** : Ajustez complexité selon l'audience
6. **Liberté structurelle** : Vous décidez librement du nombre de sections (1 à 7) selon ce qui est naturel pour le récit. Un récit court peut n'avoir qu'une seule section continue.

RÈGLE ABSOLUE — RIGUEUR HISTORIQUE :
- Basez vos titres de sections et éléments narratifs UNIQUEMENT sur le contexte historique fourni.
- N'INVENTEZ JAMAIS de dates, noms de personnes, lieux ou événements historiques précis.
- Si le contexte est insuffisant, utilisez des formulations vagues.
- Les éléments narratifs (atmosphères, émotions) peuvent être créatifs, mais les FAITS doivent être traçables aux sources fournies.

## Functions

### create_narrative_structure

Crée la structure narrative complète pour un scénario.

**Input** : 
```json
{
  "config": dict,
  "scenario_num": int,
  "audio_metadata": list  // transcriptions audio disponibles (même format que pour Agent 2)
}
```

**Output** : Structure JSON complète

**Usage** : Pour chaque scénario à générer

**Comportement** :
- Analyse la durée totale et les paramètres de configuration
- Décide **librement** du nombre de sections (1 à 7) — pas de règles fixes
- Lit l'`angle_scenarisation` et structure les sections pour le servir (ex: "journée_type" → sections calquées sur les heures du jour)
- Lit le `original_prompt` de l'utilisateur pour respecter ses intentions
- Intègre les archives audio dans les éléments nécessaires si disponibles
- Définit la fonction narrative de chaque section
- Crée l'arc émotionnel avec positions clés
- Planifie les transitions principales (fluidité > rupture)
- Génère notes de production insistant sur la continuité narrative

**Structure retournée** :
```json
{
  "scenario_id": 1,
  "titre_global": "Voix des quais : fragments de mémoire ouvrière",
  "axe_narratif": "travailleur",
  "angle_scenarisation": "temoignage_croise",
  "duree_totale": 240.0,
  "structure": [
    {
      "partie": 1,
      "titre": "L'aube sur les chantiers",
      "duree_cible": 80.0,
      "fonction_narrative": "exposition",
      "position_arc_emotionnel": "calme_contemplatif",
      "elements_necessaires": [
        "ambiance_matinale",
        "voix_narrative_posee",
        "archive_temoignage_docker"
      ],
      "mood": "intimiste"
    }
  ],
  "arc_emotionnel_global": "progression_crescendo",
  "rythme_general": "modere",
  "transitions_cles": [
    {
      "entre_parties": [1, 2],
      "type": "progression_naturelle",
      "duree": 2.0,
      "description": "Du calme matinal à l'activité du chantier"
    }
  ],
  "notes_production": "Récit fluide et continu — les sections sont des repères de rythme, pas des coupures. L'angle témoignage croisé implique des changements de voix narratrice."
}
```

### calculate_parts_distribution

Calcule la répartition optimale des durées par partie (fonction utilitaire).

**Input** : 
```json
{
  "total_duration": int,
  "public_cible": str,
  "rythme": str,
  "structure_type": str
}
```

**Output** : Liste des durées par partie

**Usage** : Calcul automatique de la distribution temporelle (utilisé en interne ou comme fallback)

### define_emotional_arc

Définit la courbe émotionnelle du scénario.

**Input** : 
```json
{
  "tone": str,
  "structure_type": str,
  "duration": float,
  "public_cible": str
}
```

**Output** : Arc émotionnel avec positions clés

**Usage** : Planification de la progression émotionnelle

**Exemple retour** :
```json
{
  "type": "progression_crescendo",
  "points_cles": [
    {"position": 0.0, "etat": "calme", "intensite": 0.2},
    {"position": 0.4, "etat": "tension_montante", "intensite": 0.5},
    {"position": 0.75, "etat": "climax", "intensite": 0.9},
    {"position": 1.0, "etat": "resolution", "intensite": 0.4}
  ]
}
```

## Notes

### Philosophie de structuration

Le nombre de sections n'est **pas** dicté par des règles rigides. L'agent décide librement selon :
- La durée totale (un récit de 60s peut être en 1 section continue)
- L'angle de scénarisation (ex: "journée_type" → sections calquées sur matin/midi/soir)
- Le ton demandé (contemplatif = moins de sections, épique = plus de sections)
- Le public cible (enfants = sections courtes)

Les sections sont des **repères de rythme**, pas des coupures franches. Le texte final doit couler naturellement d'un bout à l'autre.

### Angle de scénarisation

L'`angle_scenarisation` définit la **manière** de raconter et influence directement la structure :

| Angle | Impact sur la structure |
|-------|----------------------|
| `temoignage_croise` | Sections = différentes voix/témoins |
| `journee_type` | Sections = moments de la journée |
| `avant_apres_evenement` | Diptyque avant/après |
| `portrait_individuel` | Arc de vie d'une personne |
| `chronique_sociale` | Progression thématique |
| `mosaique_voix` | Fragments entrelacés |
| `lettre_intime` | Flux continu possible (1-2 sections) |
| `recit_initiatique` | Étapes de découverte |

### Types d'arcs émotionnels

- **progression_crescendo** : Montée progressive vers climax
- **tension_resolution** : Tension établie puis relâchée
- **circulaire** : Retour au point de départ transformé
- **vagues** : Alternance hauts et bas
- **contemplative** : Courbe douce, pas de pic marqué

### Garde-fous anti-hallucination

- Les titres de sections doivent être basés sur le contexte historique fourni
- Aucun nom, date ou lieu inventé dans les éléments nécessaires
- Si le contexte manque → titres génériques ("Le matin", "Le travail", "Le soir")
