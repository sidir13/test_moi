# Agent 2 : Historical Scenario Writer

## Role

Scénariste historique et conteur. Reçoit soit un **prompt template pré-construit d'Agent 0** (complété avec la structure d'Agent 1), soit la structure narrative directement (legacy). Écrit le scénario complet avec texte de narration, placement des archives audio, et directions de ton. Garant de la rigueur historique.

Responsabilités :
- Écrire le texte narratif complet pour chaque partie
- Placer stratégiquement les archives audio
- Définir les moments clés et leur traitement sonore
- Calculer les durées de lecture précises
- Assurer cohérence historique (vérifier anachronismes)
- Intégrer vocabulaire d'époque avec accessibilité
- Créer metadata pour Agent 3

## Model Configuration

- Model: claude-opus-4-5
- Temperature: 0.8
- Max tokens: 8000

Raison : Opus pour qualité d'écriture supérieure, température élevée pour créativité narrative tout en maintenant cohérence.

## System Prompt

Vous êtes un auteur et historien polyvalent. Vous savez adapter votre plume à n'importe quel territoire, époque ou thématique. Votre mission est de créer des récits audio historiquement rigoureux.

Principes invariants :
1. **Écrivez pour l'oreille** : phrases fluides, rythme naturel.
2. **Respectez les durées cibles** : le nombre de mots doit correspondre à la durée demandée.
3. **Adaptez-vous** : ton, rythme, style narratif définis par la configuration — suivez-les fidèlement.

RIGUEUR HISTORIQUE (non négociable) :
- Basez-vous EXCLUSIVEMENT sur les documents, transcriptions et sources fournis.
- N'INVENTEZ JAMAIS de dates, noms, lieux ou événements absents des sources.
- Restez volontairement vague si le contexte manque.
- Atmosphères et émotions : créatives. Faits : traçables.

## Functions

### writeFromPromptTemplate ⭐ (point d'entrée principal)

Écrit un scénario complet depuis un prompt template fourni par Agent 0, complété avec la structure et le résumé d'Agent 1.

**Input** :
```json
{
  "promptTemplate": "str (template d'Agent 0 contenant <<STRUCTURE_ET_RESUME>>)",
  "structureData": "dict (sortie d'Agent 1 : structure + resumeHistoire)"
}
```

**Output** : Scénario JSON complet (voir structure retournée ci-dessous)

**Usage** : Point d'entrée principal dans le nouveau pipeline (Agent 0 → Agent 1 → Agent 2 → Agent 3).

**Comportement** :
1. Extrait le résumé et la structure des parties depuis `structureData`
2. Construit un bloc de texte lisible avec : titre, résumé, arc émotionnel, notes de production, et détails de chaque partie (durée cible, mots attendus, fonction, mood, arc, éléments)
3. Remplace `<<STRUCTURE_ET_RESUME>>` dans le template par ce bloc
4. Appelle le LLM avec le prompt complet + system prompt
5. Post-traite les parties retournées (normalisation ton, moments_cles, ambiances, sentence_sources)
6. Recalcule les durées via `calculate_narration_timing`
7. Assemble le scénario final avec metadata

**Avantage** : Le prompt contient déjà TOUS les paramètres (contexte historique, transcriptions, consignes vocales, paramètres verrouillés) grâce à Agent 0 — pas besoin de les reconstruire.

### write_complete_scenario (legacy)

Écrit le scénario complet à partir de la structure (chemin legacy).

**Input** :
```json
{
  "structure": "dict (Structure d'Agent 1)",
  "config": "dict",
  "historical_context": "dict (optionnel, contexte enrichi par skill)",
  "audio_transcriptions": "list (optionnel, archives avec transcriptions)"
}
```

**Output** : Scénario JSON complet

**Usage** : Conservé pour rétrocompatibilité. Dans le nouveau pipeline, `writeFromPromptTemplate` est préféré.

### Structure retournée (commune aux deux méthodes)

```json
{
  "scenario_id": 1,
  "titre": "La grève des dockers",
  "axe_narratif": "travailleur",
  "angle_scenarisation": "temoignage_croise",
  "resumeHistoire": "Résumé narratif de l'histoire...",
  "duree_estimee": 180.5,
  "parties": [
    {
      "partie_id": 1,
      "titre": "L'aube d'une journée ordinaire",
      "duree": 45.2,
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
          "fichier": "archive_docker_1905_temoignage.wav",
          "segment": {"start": 12.0, "end": 20.0},
          "texte_archive": "Transcription de l'archive...",
          "fade_in": 1.0,
          "fade_out": 1.0,
          "volume": 0.7,
          "processing": ["eq_vintage", "noise_reduction_light"],
          "justification_narrative": "Illustre les conditions de travail"
        }
      ],
      "ambiances_continues": [
        {
          "son": "port_ambiance_morning.wav",
          "start": "0:00",
          "end": "0:45",
          "volume": 0.3,
          "description": "Ambiance portuaire matinale"
        }
      ],
      "sentence_sources": [
        {
          "sentence": "En ce matin de février 1905...",
          "sources": ["Archives Municipales"]
        }
      ]
    }
  ],
  "metadata": {
    "nombre_mots": 1250,
    "duree_lecture_estimee": 180.5,
    "nombre_archives_utilisees": 3,
    "nombre_ambiances": 5
  },
  "notes_pour_agent_3": "Privilégier ambiances naturelles en partie 1..."
}
```

### validate_historical_accuracy

Vérifie dates, lieux, vocabulaire pour cohérence historique.

**Input** :
```json
{
  "scenario": "dict",
  "period": {"start_year": "int", "end_year": "int"},
  "strict_mode": "bool"
}
```

**Output** : Validation result avec score, erreurs, warnings

**Usage** : Après écriture, utilisé dans le chemin legacy

**Comportement** :
- Utilise le skill `historical_context_analyzer.detect_anachronisms` si disponible
- Vérifie cohérence des dates mentionnées
- Valide les localisations
- Calcule un score d'exactitude (0.0-1.0)

### calculate_narration_timing

Calcule durée de lecture précise avec pauses.

**Input** :
```json
{
  "text": "str",
  "tempo_wpm": "int (mots par minute)",
  "pauses": "list (pauses avec durées)",
  "include_buffer": "bool (ajouter 10% buffer)"
}
```

**Output** :
```json
{
  "duration": 45.5,
  "word_count": 125,
  "reading_time": 41.5,
  "pauses_time": 4.0,
  "buffer": 0.0
}
```

**Tempos standards** :
- Très lent (contemplatif) : 90-100 WPM
- Lent (posé) : 100-110 WPM
- Modéré : 110-130 WPM
- Rapide (dynamique) : 130-150 WPM
- Très rapide (urgent) : 150-170 WPM

## Notes

### Placement des archives audio

**Principes** :
1. **Illustration, pas interruption** : L'archive enrichit le récit, ne le coupe pas
2. **Contexte avant archive** : Toujours présenter avant de faire entendre
3. **Résonance après archive** : Laisser un silence ou commentaire
4. **Durée adaptée** : Max 10-15s par archive pour maintenir rythme
5. **Qualité variable** : Assumer le grain vintage, ajouter processing si besoin

### Vocabulaire d'époque vs accessibilité

**Stratégie selon `authenticite_vs_accessibilite`** :

**Haute authenticité (> 0.8)** :
- Vocabulaire d'époque préservé
- Expressions idiomatiques conservées

**Équilibré (0.5-0.8)** :
- Termes d'époque + explication contextuelle
- Ex: "Les portefaix, ces travailleurs du port..."

**Haute accessibilité (< 0.5)** :
- Termes modernes équivalents
- Simplifications assumées

### Post-traitement des parties

Agent 2 normalise automatiquement la sortie du LLM :
- `ton` : convertit en dict si le LLM retourne une string
- `moments_cles` : filtre les éléments non-dict
- `ambiances_continues` : filtre les éléments non-dict
- `sentence_sources` : normalise les entrées (sentence + sources)
- Recalcule la durée de chaque partie via `calculate_narration_timing`

### Gestion des erreurs

**Si historical_context manquant** :
- Utiliser connaissances générales de la période
- Ajouter disclaimer en metadata

**Si audio_transcriptions vide** :
- Créer scénario sans archives
- Suggérer ambiances et effets alternatifs

**Si dépassement de durée** :
- Réduire parties proportionnellement
- Éliminer détails secondaires
