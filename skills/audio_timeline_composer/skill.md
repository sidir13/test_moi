# Audio Timeline Composer

## Role

Composition de timelines audio précises, résolution des overlaps, application des règles de mixing. Utilisé par Agent 3 pour créer la timeline technique finale.

## Model Configuration

- Model: claude-sonnet-4-5
- Temperature: 0.2
- Max tokens: 4000

## Python Tools

Enabled: true - Calculs de timing précis, détection overlaps

## Functions

### create_audio_tracks

Crée la structure de tracks depuis le scénario.

**Input** : `{"scenario": dict, "track_types": list}`
**Output** : Dict de tracks (narration, archives, ambiances, SFX, musique)

### resolve_track_overlaps

Résout les conflits temporels entre régions.

**Input** : `{"tracks": dict}`
**Output** : Tracks ajustés avec transitions automatiques

### apply_mixing_rules

Applique règles de mixing (volumes, ducking, EQ).

**Input** : `{"tracks": dict, "rules": dict}`
**Output** : Tracks avec volumes et effets optimisés
