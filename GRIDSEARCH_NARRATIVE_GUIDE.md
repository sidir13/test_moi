# Guide Gridsearch - Paramètres Narratifs

## 🎯 Objectif

Ce gridsearch teste l'impact des **paramètres narratifs** sur la qualité des scénarios générés, plutôt que les paramètres techniques du LLM.

## 📊 Paramètres Testés

Le gridsearch fait varier les paramètres suivants de configuration :

### 1. **Ton** (`ton`)
Le ton émotionnel et stylistique du récit.

Options :
- `neutre_informatif` : Factuel, objectif
- `dramatique_immersif` : Intense, captivant
- `intimiste_confidentiel` : Personnel, proche
- `emotionnel_personnel` : Émotif, subjectif
- `poetique_contemplatif` : Lyrique, réflexif
- `journalistique_factuel` : Neutre, journalistique
- `pedagogique_accessible` : Clair, didactique

### 2. **Forme** (`forme`)
Le format narratif du contenu.

Options :
- `documentaire` : Format documentaire classique
- `conte` : Récit narratif, storytelling
- `podcast_narratif` : Style podcast audio
- `temoignage` : Témoignage direct
- `interview` : Format interview
- `reportage` : Reportage journalistique
- `fiction_historique` : Fiction basée sur l'histoire

### 3. **Structure narrative** (`structure_narrative`)
L'organisation temporelle du récit.

Options :
- `chronologique` : Ordre chronologique linéaire
- `flashback` : Retours en arrière
- `thematique` : Organisation par thème
- `crescendo_emotionnel` : Montée émotionnelle
- `mosaique` : Fragments entrecroisés
- `circulaire` : Structure en boucle

### 4. **Époque linguistique** (`epoque_linguistique`)
Le style de langage utilisé.

Options :
- `authentique` : Vocabulaire d'époque strict
- `modernise_accessible` : Langage moderne
- `mixte` : Mélange équilibré

### 5. **Niveau de détail historique** (`niveau_detail_historique`)
La profondeur des informations historiques.

Options :
- `leger` : Informations de base
- `moyen` : Détails modérés
- `approfondi` : Analyse détaillée
- `academique` : Niveau universitaire

### 6. **Perspective narrative** (`perspective_narrative`)
Le point de vue narratif.

Options :
- `premiere_personne` : "Je"
- `troisieme_personne` : "Il/Elle"
- `voix_off_omnisciente` : Narrateur omniscient
- `chorale_multiple_voix` : Plusieurs voix

### 7. **Rythme** (`rythme`)
Le tempo et la cadence du récit.

Options :
- `lent_contemplatif` : Lent, méditatif
- `modere` : Rythme équilibré
- `dynamique` : Rapide, énergique
- `varie` : Variations de rythme

## 🚀 Utilisation

### Mode RAPIDE (2 tests, ~15-30min)
Parfait pour tester rapidement :

```bash
python gridsearch_local.py --quick
```

Teste seulement :
- 2 tons (neutre vs dramatique)
- 1 forme (documentaire)
- Autres paramètres fixes

### Mode STANDARD (18 tests, ~1-2h) ⭐ Recommandé
Exploration équilibrée :

```bash
python gridsearch_local.py
```

Teste :
- 3 tons différents
- 3 formes différentes
- 2 structures narratives
- Autres paramètres fixes

### Mode COMPLET (50 tests, ~6-10h)
Validation exhaustive :

```bash
python gridsearch_local.py --full
```

Teste un échantillon stratifié de 50 combinaisons parmi :
- 4 tons
- 4 formes
- 4 structures
- 3 époques linguistiques
- 3 niveaux de détail
- 2 perspectives
- 3 rythmes

### Avec un prompt personnalisé

```bash
python gridsearch_local.py "Créer un conte de 4 minutes sur les chantiers navals"
```

## 📁 Résultats

### Structure des dossiers

```
output/gridsearch/run_YYYYMMDD_HHMMSS/
├── gridsearch_config.json              # Configuration du run
├── comparison_report.json              # Rapport complet (JSON)
├── comparison_report.txt               # Rapport lisible (TXT)
├── test_001_neutre_documentaire_chronologique/
│   ├── config.json                     # Config générée
│   ├── structure.json                  # Structure narrative
│   ├── scenario.json                   # Scénario complet
│   ├── timeline.json                   # Timeline audio
│   └── metadata.json                   # Métriques du test
├── test_002_dramatique_conte_flashback/
│   └── ...
└── ...
```

### Rapport de comparaison

Le fichier `comparison_report.txt` contient :

1. **Vue d'ensemble** : Taux de succès global
2. **Résultats par test** : Détails de chaque configuration
3. **Analyse par paramètre** : Impact de chaque paramètre sur :
   - Taux de succès
   - Nombre de mots moyen
   - Durée moyenne du scénario

Exemple :

```
TON:
----------------------------------------
  • neutre_informatif:
      Succès: 100.0%
      Mots moyen: 387
      Durée moyenne: 238.5s
  • dramatique_immersif:
      Succès: 100.0%
      Mots moyen: 412
      Durée moyenne: 245.2s
  • intimiste_confidentiel:
      Succès: 100.0%
      Mots moyen: 395
      Durée moyenne: 240.8s
```

## 📈 Analyse des Résultats

### Métriques collectées

Pour chaque test, on collecte :

- ✅ **Succès/Échec** : Le test s'est-il exécuté sans erreur ?
- 📝 **Nombre de mots** : Longueur du scénario
- ⏱️ **Durée estimée** : Durée audio prévue
- 🏗️ **Nombre de parties** : Découpage du scénario
- ⚡ **Temps de génération** : Durée pour chaque agent

### Questions à explorer

1. **Quel ton génère les meilleurs scénarios ?**
   - Comparer le nombre de mots, la durée
   - Évaluer subjectivement la qualité narrative

2. **Quelle forme est la plus adaptée ?**
   - Le conte produit-il des textes plus longs ?
   - Le podcast est-il plus concis ?

3. **Impact de la structure narrative ?**
   - Le flashback complexifie-t-il la génération ?
   - La structure chronologique est-elle plus fiable ?

4. **Époque linguistique vs accessibilité ?**
   - Le vocabulaire authentique rallonge-t-il les textes ?
   - Le langage moderne facilite-t-il la génération ?

5. **Niveau de détail optimal ?**
   - Trop de détails ralentit-il la génération ?
   - Le niveau léger perd-il en richesse ?

## 🔧 Configuration Avancée

### Modifier les grilles de test

Éditez directement dans `gridsearch_local.py` :

```python
PARAM_GRID = {
    'ton': ["neutre_informatif", "dramatique_immersif"],
    'forme': ["documentaire", "conte"],
    # Ajoutez d'autres paramètres...
}
```

### Limiter le nombre de tests en mode FULL

Par défaut, le mode FULL génère max 50 combinaisons. Pour changer :

```python
# Dans la fonction main()
combinations = generate_param_combinations(param_grid, max_combinations=100)
```

## 📊 Différence avec gridsearch_groq.py

| Aspect | gridsearch_local.py | gridsearch_groq.py |
|--------|---------------------|---------------------|
| **Cible** | Paramètres narratifs | Modèles LLM + paramètres |
| **Focus** | Ton, forme, structure | Température, modèle, top_p |
| **Modèle** | Ollama local fixe | Groq (cloud) variable |
| **Objectif** | Optimiser le contenu | Optimiser le moteur LLM |
| **Coût** | Gratuit (local) | Payant (API) |
| **Durée** | Plus long (local) | Plus rapide (cloud) |

## 💡 Bonnes Pratiques

1. **Commencez par --quick** : Validez que tout fonctionne
2. **Utilisez un prompt représentatif** : Testez sur un cas d'usage réel
3. **Analysez progressivement** : Mode quick → standard → full
4. **Documentez vos observations** : Notez les meilleures combinaisons
5. **Comparez avec vos attentes** : Le ton dramatique est-il vraiment plus dramatique ?

## 🐛 Dépannage

### Le test échoue systématiquement

- Vérifiez qu'Ollama est lancé : `curl http://localhost:11434`
- Vérifiez que le modèle est téléchargé : `ollama list`
- Vérifiez les logs dans `logs/memoire_territoires.log`

### Les résultats sont très similaires

- Augmentez la variation des paramètres testés
- Vérifiez que les paramètres sont bien appliqués dans la config
- Certains paramètres ont un impact subtil, analysez en détail

### Trop long

- Utilisez `--quick` pour débugger
- Réduisez la grille de paramètres
- Lancez pendant la nuit pour le mode FULL

## 📚 Ressources

- Configuration par défaut : `config/default_config.json`
- Documentation des agents : `agents.md`
- Guide Groq : `GUIDE_GROQ.md`

---

**Bonne exploration ! 🚀**
