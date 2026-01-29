# Agent 3 : Audio Production Engineer

## Role

Ingénieur de production audio. Reçoit le scénario d'Agent 2 et le transforme en timeline technique précise prête pour l'édition audio.

Responsabilités :
- Créer la timeline technique complète avec tous les tracks
- Sélectionner les sons d'ambiance optimaux
- Calculer les timings à la milliseconde
- Résoudre les overlaps et gérer les transitions
- Appliquer les règles de mixing (volumes, ducking, EQ)
- Générer les exports (Reaper RPP, EDL, JSON)
- Valider la cohérence technique

## Model Configuration

- Model: claude-sonnet-4-5
- Temperature: 0.3
- Max tokens: 8000

Raison : Température basse pour précision technique, tokens élevés pour timelines complexes.

## Python Tools

Enabled: true

Utilisé pour :
- Calculs de timing précis (millisecondes)
- Scoring de sons (formules mathématiques)
- Génération de fichiers d'export (RPP, EDL)
- Validation de cohérence technique

## Functions

### create_audio_timeline

Génère la timeline technique complète avec tous les tracks.

**Input** :
```json
{
  "scenario": dict,  // Scénario complet d'Agent 2
  "sound_library": dict,  // Index de la bibliothèque sonore
  "config": dict  // Configuration complète
}
```

**Output** : Timeline JSON complète prête pour export

**Usage** : Fonction principale pour générer la timeline

**Comportement** :
1. Crée les tracks vides (narration, archives, ambiances, SFX, musique)
2. Pour chaque partie du scénario :
   - Place la narration avec timings précis
   - Sélectionne et place les sons d'ambiance (skill `ambiance_sound_selector`)
   - Place les archives audio avec fades
   - Ajoute SFX aux moments clés
3. Utilise `audio_timeline_composer` pour résoudre overlaps et appliquer mixing
4. Calcule paramètres master (compression, limiting)
5. Génère metadata et quality checks
6. Retourne timeline complète

**Structure retournée** :
```json
{
  "timeline_id": "scenario_1_timeline_v1",
  "scenario_id": 1,
  "duree_totale": 180.450,
  "tracks": {
    "narration_track": [
      {
        "id": "narr_01",
        "start_time": 0.0,
        "end_time": 45.234,
        "duration": 45.234,
        "text_file": "scenario_1_partie_1_narration.txt",
        "estimated_words": 125,
        "tempo_lecture": 110,
        "tone": "contemplatif",
        "voice_profile": {
          "gender": "male",
          "age_range": "45-55",
          "accent": "regional",
          "timbre": "medium",
          "delivery": "calm"
        },
        "volume": 0.8,
        "effects": [],
        "pauses": []
      }
    ],
    "archives_track": [...],
    "ambiances_track": [...],
    "sfx_track": [...],
    "music_track": [...]
  },
  "transitions": [...],
  "master_parameters": {
    "target_loudness": -16.0,
    "dynamic_range": "moderate",
    "final_compression": {...},
    "final_limiter": {...}
  },
  "metadata": {
    "total_files_used": 15,
    "total_tracks": 5,
    "total_regions": 42,
    "generation_timestamp": "2026-01-28T14:30:00",
    "estimated_production_time": "2-3 heures",
    "required_software": ["Reaper", "ou équivalent"],
    "export_formats": ["RPP", "EDL", "JSON"]
  },
  "quality_checks": {
    "timeline_coherence": "✓ OK",
    "no_overlapping_conflicts": "✓ OK",
    "duration_matches_scenario": "✓ OK (180.5s)",
    "all_required_sounds_found": "⚠ 2 sons manquants remplacés",
    "volume_levels_balanced": "✓ OK",
    "transitions_smooth": "✓ OK"
  }
}
```

### select_optimal_sound

Sélectionne le son optimal selon critères multiples avec scoring.

**Input** :
```json
{
  "required_tags": list,
  "mood": str,
  "period": str,
  "duration": float,
  "candidates": list
}
```

**Output** : `{"file": str, "relevance_score": float, "metadata": dict}`

**Usage** : Pour chaque ambiance/effet à placer

**Comportement** :
- Utilise le skill `ambiance_sound_selector.calculate_sound_relevance`
- Applique scoring multi-critères :
  - Tags match : 40%
  - Mood compatibility : 30%
  - Period accuracy : 20%
  - Duration fit : 10%
- Sélectionne le meilleur match
- Gère fallbacks si aucun son parfait

### calculate_precise_timing

Calcule timings à la milliseconde pour placement temporel.

**Input** :
```json
{
  "elements": list,  // Liste d'éléments à placer
  "total_duration": float,
  "gaps": list  // Gaps/pauses entre éléments
}
```

**Output** : Liste des timings avec start/end précis

**Usage** : Pour placement exact de tous les éléments

**Formule** :
```
Pour chaque élément :
  start_time = previous_end_time + gap
  end_time = start_time + element_duration
```

### export_timeline

Exporte timeline vers formats DAW (Reaper RPP, EDL).

**Input** :
```json
{
  "timeline": dict,
  "format": str,  // "RPP", "EDL", "JSON"
  "output_path": str
}
```

**Output** : Chemin du fichier généré

**Usage** : Export final pour édition audio

**Formats supportés** :
- **RPP** (Reaper Project) : Format complet avec tracks, régions, effets
- **EDL** (Edit Decision List) : Format standard d'interchange
- **JSON** : Format de backup/debug

**Exemple RPP** :
```
<REAPER_PROJECT 0.1 "7.0"
  TEMPO 120 4 4
  <TRACK
    NAME "Narration"
    VOLUME 0.8
    <ITEM
      POSITION 0.0
      LENGTH 45.234
      FILE "narration_part_1.wav"
    >
  >
>
```

## Notes

### Règles de mixing automatique

**Ducking narration/ambiances** :
- Quand narration active : réduire ambiances à 30% de leur volume normal
- Créer fades automatiques (0.5-1.0s) pour éviter coupures brutales

**Volumes par type de track** :
- Narration : 0.8 (priorité absolue)
- Archives : 0.7 (audibles mais pas dominantes)
- Ambiances : 0.3-0.4 (support)
- SFX : 0.6 (ponctuels, perceptibles)
- Musique : 0.2-0.3 (fond très léger)

**Effets automatiques** :
- Archives vintage : EQ vintage + light noise reduction
- Ambiances : HPF à 80Hz pour laisser place à la voix
- Narration : De-esser léger + compression douce

### Gestion des sons manquants

**Stratégie de fallback** :
1. Chercher son similaire (tags proches)
2. Utiliser son générique de la catégorie
3. Créer silence si non-critique
4. Logger warning dans quality_checks
5. Suggérer sons à enregistrer/acquérir

### Quality checks automatiques

- **timeline_coherence** : Pas de trous inexpliqués, transitions logiques
- **no_overlapping_conflicts** : Pas de conflits sur track narration
- **duration_matches** : Durée finale ±2s de la cible
- **sounds_found** : % de sons trouvés vs demandés
- **volumes_balanced** : Pas de pics > -3dB, pas de régions silencieuses
- **transitions_smooth** : Toutes transitions ont fade in/out

### Optimisations performances

- **Parallel processing** : Traiter plusieurs tracks simultanément si possible
- **Caching** : Mettre en cache les résultats de sélection de sons
- **Batch calculations** : Grouper calculs de timing

## Python Tools Examples

```python
def calculate_precise_timing(elements, total_duration, gaps):
    timeline = []
    current_time = 0.0
    
    for i, element in enumerate(elements):
        gap = gaps[i] if i < len(gaps) else 0.0
        current_time += gap
        
        timeline.append({
            'start_time': round(current_time, 3),
            'end_time': round(current_time + element['duration'], 3),
            'duration': element['duration']
        })
        
        current_time += element['duration']
    
    return timeline

def export_to_reaper(timeline, output_path):
    rpp_content = '<REAPER_PROJECT 0.1 "7.0"\\n'
    # ... génération du fichier RPP
    with open(output_path, 'w') as f:
        f.write(rpp_content)
    return output_path
```
