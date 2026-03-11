# Agent 3 : Audio Tag Engineer (ElevenLabs)

## Role

Ingénieur de balisage audio. Reçoit le scénario d'Agent 2 et le transforme en **texte balisé** prêt pour la synthèse vocale ElevenLabs et le design sonore.

Responsabilités :
- Insérer des **balises vocales ElevenLabs** `[]` dans le texte narratif pour guider la voix TTS
- Insérer des **marqueurs de sons d'ambiance** `{}` aux endroits stratégiques
- Préserver intégralement le texte narratif (aucune réécriture)
- Adapter l'intensité des balises au ton de chaque partie
- Séparer le texte balisé par parties pour un traitement granulaire

## Model Configuration

- Model: claude-sonnet-4-5
- Temperature: 0.3
- Max tokens: 8000

Raison : Température basse pour précision technique du balisage, tokens élevés pour traiter des scénarios complets.

## System Prompt

Vous êtes un ingénieur de production audio spécialisé dans le balisage de textes pour la synthèse vocale (ElevenLabs) et le design sonore.

Votre rôle est de prendre un scénario narratif et d'y insérer :
1. Des **balises vocales ElevenLabs** entre crochets [] — elles indiquent au moteur TTS comment prononcer le texte.
   Exemples : [pause 2s], [rire], [murmure], [stupeur], [ton grave], [ton joyeux], [acceleration], [ralentissement], [soupir], [voix forte], [chuchotement], [ton solennel], [hésitation], [émotion contenue], [colère], [tristesse].
2. Des **marqueurs de sons d'ambiance** entre accolades {} — ils indiquent où insérer des fichiers audio d'ambiance.
   Exemples : {ambiance_port_brume.wav}, {foule_agitee.wav}, {clapotis_eau.wav}, {vent_mer.wav}, {pas_sur_paves.wav}.

Règles :
- Insérez les balises [] DANS le texte, au bon endroit pour que la lecture soit naturelle.
- Les balises {sons} peuvent être placées en début de paragraphe ou à des transitions narratives.
- Ne modifiez JAMAIS le texte narratif lui-même (pas de réécriture).
- Soyez subtil : pas trop de balises — un balisage excessif nuit à la qualité.
- Nommez les fichiers d'ambiance de manière descriptive : snake_case, extension .wav.
- Adaptez l'intensité et le type des balises au ton du scénario.

## Functions

### formatWithTags ⭐ (point d'entrée principal)

Annote le texte narratif d'un scénario avec des balises ElevenLabs et des marqueurs d'ambiance.

**Input** :
```json
{
  "scenario": "dict (scénario complet d'Agent 2 avec 'parties' contenant 'texte_narration')",
  "config": "dict (optionnel, config pipeline — utilisé pour voice_instructions, ton, etc.)"
}
```

**Output** :
```json
{
  "scenario_id": 1,
  "titre": "Voix des quais",
  "taggedText": "=== PARTIE 1 : L'aube ===\n{ambiance_port_brume.wav}\n[ton grave] En ce matin de février... [pause 2s] Les pavés luisent...",
  "parties": [
    {
      "partie_id": 1,
      "titre": "L'aube",
      "taggedText": "{ambiance_port_brume.wav}\n[ton grave] En ce matin de février... [pause 2s] Les pavés luisent..."
    }
  ],
  "metadata": {
    "voiceTags": 12,
    "soundTags": 4,
    "originalWordCount": 387
  }
}
```

**Usage** : Point d'entrée unique dans le pipeline (Agent 2 → Agent 3).

**Comportement** :
1. Extrait le contexte : `voice_instructions`, `ton`, `notes_pour_agent_3`
2. Pour chaque partie du scénario, collecte :
   - Texte narratif
   - Ton (global + intonation)
   - Ambiances suggérées par Agent 2
   - Moments clés
3. Assemble le texte complet avec des marqueurs `=== PARTIE N : Titre ===`
4. Construit un prompt via `_buildTaggingPrompt` avec le texte + contexte
5. Appelle le LLM qui insère les balises `[]` et `{}` dans le texte
6. Sépare le texte balisé par parties via `_splitTaggedTextByParts`
7. Compte les balises et retourne le résultat structuré

**Fallback** : En cas d'erreur, retourne le texte original non balisé avec metadata d'erreur.

### create_audio_timeline (legacy — déprécié)

Génère une timeline technique complète avec tous les tracks (narration, archives, ambiances, SFX, musique).

**Usage** : Conservé pour rétrocompatibilité uniquement. Émet un warning si appelé.

## Types de balises

### Balises vocales ElevenLabs `[]`

Insérées **dans** le texte narratif pour guider la synthèse vocale :

| Balise | Description | Exemple d'usage |
|--------|------------|-----------------|
| `[pause 2s]` | Pause de N secondes | Après une phrase forte, avant une révélation |
| `[rire]` | Rire du narrateur | Moment léger, anecdote amusante |
| `[murmure]` | Passage murmuré | Ton confidentiel, secret |
| `[stupeur]` | Stupéfaction | Annonce surprenante |
| `[ton grave]` | Voix grave, solennelle | Moments dramatiques, annonces sombres |
| `[ton joyeux]` | Voix joyeuse | Célébration, bonne nouvelle |
| `[acceleration]` | Accélération du débit | Tension montante, urgence |
| `[ralentissement]` | Ralentissement du débit | Moments contemplatifs, conclusions |
| `[soupir]` | Soupir | Lassitude, résignation, soulagement |
| `[voix forte]` | Volume élevé | Cris, discours, emphase |
| `[chuchotement]` | Voix très basse | Intimité, secret, peur |
| `[ton solennel]` | Ton cérémonieux | Hommages, moments historiques |
| `[hésitation]` | Hésitation vocale | Doute, émotion qui submerge |
| `[émotion contenue]` | Émotion retenue | Moments poignants sans dramatisation |
| `[colère]` | Voix en colère | Injustice, révolte |
| `[tristesse]` | Voix triste | Perte, nostalgie |

### Marqueurs de sons d'ambiance `{}`

Placés en début de paragraphe ou aux transitions narratives :

| Format | Description | Exemple |
|--------|------------|---------|
| `{nom_descriptif.wav}` | Fichier d'ambiance | `{ambiance_port_brume.wav}` |

**Convention de nommage** :
- snake_case
- Extension `.wav`
- Nom descriptif du son : `{foule_agitee.wav}`, `{vent_mer.wav}`, `{pas_sur_paves.wav}`, `{cloches_eglise.wav}`

## Règles de balisage

1. **Subtilité** : Maximum 2-3 balises vocales par paragraphe, 1-2 sons d'ambiance par partie
2. **Préservation** : Le texte narratif ne doit JAMAIS être modifié — uniquement des balises ajoutées
3. **Cohérence** : Les balises doivent correspondre au ton de chaque partie
4. **Marqueurs de partie** : Les séparateurs `=== PARTIE N : Titre ===` sont conservés pour permettre le re-découpage
5. **Adaptation** : Les consignes vocales de l'utilisateur (si fournies) sont prioritaires

## Notes

### Flux de données Agent 2 → Agent 3

Agent 3 exploite les informations suivantes du scénario :
- `parties[].texte_narration` : le texte brut à baliser
- `parties[].ton.global` et `parties[].ton.intonation` : guide le choix des balises vocales
- `parties[].ambiances_continues` : suggestions d'ambiances d'Agent 2
- `parties[].moments_cles` : indications de moments à marquer
- `notes_pour_agent_3` : directives spéciales de production

### Contexte supplémentaire depuis la config

- `config.voice_instructions` : consignes vocales spécifiques de l'utilisateur
- `config.scenario_config.generation_parameters.ton.value` : ton global du scénario

### Gestion des erreurs

**Si le LLM ne retourne pas un texte balisé correct** :
- Retourne le texte original non balisé
- Metadata contient `error` avec le message d'erreur
- `voiceTags` et `soundTags` à 0

**Si les marqueurs de partie sont absents du texte balisé** :
- Le texte complet est assigné à la première partie
- Les autres parties reçoivent un texte vide

### Migration depuis l'ancienne architecture

L'Agent 3 a été **refondu** depuis une architecture de timeline audio technique vers une architecture de balisage ElevenLabs :

| Avant (legacy) | Après (actuel) |
|----------------|----------------|
| `create_audio_timeline` | `formatWithTags` |
| Timeline JSON multi-tracks | Texte balisé `[]` et `{}` |
| Sélection de sons dans une bibliothèque | Suggestions de noms de fichiers d'ambiance |
| Calculs de timing à la milliseconde | Balisage sémantique pour TTS |
| Export Reaper/EDL | Texte prêt pour ElevenLabs |

Les méthodes legacy (`create_audio_timeline`, `_create_narration_region`, etc.) sont conservées pour rétrocompatibilité mais émettent un warning.
