# Historical Context Analyzer

## Role

Analyse des documents historiques, extraction de contexte enrichi et détection d'anachronismes. Ce skill est utilisé par Agent 2 pour garantir la rigueur historique.

Responsabilités :
- Analyser documents et sources historiques
- Extraire vocabulaire d'époque
- Identifier dates, lieux, personnages clés
- Détecter anachronismes dans les textes
- Enrichir le contexte historique

## Model Configuration

- Model: claude-sonnet-4-5
- Temperature: 0.2
- Max tokens: 4000

Raison : Température basse pour précision factuelle et analyse rigoureuse.

## Functions

### analyze_historical_documents

Analyse des documents historiques pour extraire contexte enrichi.

**Input** : 
```json
{
  "documents": list,  // Liste de documents textuels
  "period": {"start_year": int, "end_year": int},
  "location": str,
  "themes": list
}
```

**Output** : Contexte historique enrichi

**Usage** : Avant écriture par Agent 2, pour enrichir le contexte

**Comportement** :
- Extrait dates, événements, personnages mentionnés
- Identifie le vocabulaire d'époque
- Crée un glossaire de termes historiques
- Liste les sources par crédibilité
- Génère des recommandations pour la narration

**Structure retournée** :
```json
{
  "contexte_enrichi": {
    "dates_cles": [{"date": "1905-02-12", "evenement": "Début de la grève"}],
    "personnages": [{"nom": "Jean Dupont", "role": "Délégué syndical"}],
    "lieux_detailles": ["Quai de la Fosse", "Halle aux marchandises"],
    "vocabulaire_epoque": {
      "termes_professionnels": ["docker", "portefaix", "débardeur"],
      "expressions": ["faire la belle"],
      "unites_mesure": ["tonneau", "quintal"]
    },
    "contexte_social": "Description du contexte social...",
    "sources_citees": ["Archives Municipales, registre X", "Témoignage Y"]
  },
  "recommendations": [
    "Utiliser 'docker' plutôt que 'manutentionnaire'",
    "Mentionner les conditions de travail typiques"
  ]
}
```

### detect_anachronisms

Détecte les mots ou expressions anachroniques dans un texte.

**Input** : 
```json
{
  "text": str,
  "period_start": int,
  "strict_mode": bool  // optionnel, défaut false
}
```

**Output** : Liste des anachronismes détectés

**Usage** : Validation post-écriture par Agent 2

**Comportement** :
- Scanne le texte pour mots anachroniques évidents
- En mode strict : détecte également expressions modernes
- Suggère alternatives d'époque
- Classe par gravité (critique, modéré, mineur)

**Exemple retour** :
```json
{
  "anachronisms_found": [
    {
      "word": "ordinateur",
      "position": 245,
      "gravity": "critique",
      "reason": "Technologie inexistante en 1905",
      "suggestion": "Supprimer ou remplacer par 'registre'"
    },
    {
      "word": "globalisation",
      "position": 512,
      "gravity": "modéré",
      "reason": "Concept anachronique",
      "suggestion": "Utiliser 'commerce international'"
    }
  ],
  "score": 0.85,  // 1.0 = parfait, 0.0 = très anachronique
  "verdict": "acceptable_avec_corrections"
}
```

### extract_period_vocabulary

Extrait et construit un vocabulaire typique d'une période.

**Input** :
```json
{
  "period": {"start_year": int, "end_year": int},
  "domain": str,  // ex: "maritime", "industriel", "social"
  "sources": list
}
```

**Output** : Glossaire de vocabulaire d'époque

**Usage** : Préparation pour Agent 2

## Notes

### Sources de référence

Le skill peut s'appuyer sur :
- Base de données de vocabulaire historique intégrée
- Documents fournis par l'utilisateur
- Sources validées de la configuration

### Niveaux de rigueur

- **Strict** : Rejet de tout terme post-période
- **Modéré** : Accepte termes légèrement anachroniques si accessibilité
- **Souple** : Privilégie compréhension moderne

Le niveau dépend du paramètre `authenticite_vs_accessibilite` de la config.
