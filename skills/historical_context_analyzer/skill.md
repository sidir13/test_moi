# Historical Context Analyzer

## Role

Analyse des documents historiques, extraction de contexte enrichi et détection d'anachronismes. Ce skill est utilisé par Agent 2 pour garantir la rigueur historique.

Responsabilités :
- Analyser documents et sources historiques fournis par l'utilisateur
- **Fallback Wikipedia** : si aucun document n'est fourni, récupérer automatiquement des articles Wikipedia comme sources externes vérifiées
- Extraire vocabulaire d'époque
- Identifier dates, lieux, personnages clés
- Détecter anachronismes dans les textes
- Enrichir le contexte historique
- **Garantir la traçabilité** : chaque fait extrait doit être rattaché à une source

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
  "documents": list,
  "period": {"start_year": int, "end_year": int},
  "location": str,
  "themes": list
}
```

**Output** : Contexte historique enrichi

**Usage** : Avant écriture par Agent 2, pour enrichir le contexte

**Comportement** :
- Si `documents` est vide → déclenche le **fallback Wikipedia** automatiquement
- Extrait dates, événements, personnages mentionnés **uniquement** depuis les documents fournis
- Identifie le vocabulaire d'époque
- Crée un glossaire de termes historiques
- Liste les sources par crédibilité
- Génère des recommandations pour la narration

**Garde-fou anti-hallucination** :
Le prompt contient une règle absolue : « N'ajoutez AUCUNE information qui ne provient pas directement des documents ci-dessus. Ne complétez pas avec vos connaissances internes. Si un champ manque d'information, laissez-le vide plutôt que de l'inventer. »

**Structure retournée** :
```json
{
  "contexte_enrichi": {
    "dates_cles": [{"date": "YYYY-MM-DD", "evenement": "..."}],
    "personnages": [{"nom": "...", "role": "..."}],
    "lieux_detailles": ["lieu1", "lieu2"],
    "vocabulaire_epoque": {
      "termes_professionnels": ["terme1", "terme2"],
      "expressions": ["expression1"],
      "unites_mesure": ["unité1"]
    },
    "contexte_social": "Description...",
    "sources_citees": ["source1", "source2"]
  },
  "recommendations": ["rec1", "rec2"]
}
```

### detect_anachronisms

Détecte les mots ou expressions anachroniques dans un texte.

**Input** : 
```json
{
  "text": str,
  "period_start": int,
  "strict_mode": bool
}
```

**Output** : Liste des anachronismes détectés

**Usage** : Validation post-écriture par Agent 2

**Comportement** :
- Scanne le texte pour mots anachroniques évidents (base de données interne)
- En mode strict : détecte également expressions modernes
- Suggère alternatives d'époque
- Classe par gravité (critique, modéré, mineur)
- Calcule un score (1.0 = parfait, 0.0 = très anachronique)

### extract_period_vocabulary

Extrait et construit un vocabulaire typique d'une période et d'un domaine.

**Input** :
```json
{
  "period": {"start_year": int, "end_year": int},
  "domain": str,
  "sources": list
}
```

**Output** : Glossaire de vocabulaire d'époque

## Notes

### Fallback Wikipedia

Quand aucun document utilisateur n'est fourni :
1. Le skill utilise `WikipediaContextFetcher` pour chercher des articles pertinents
2. Les articles sont récupérés en français via l'API Wikipedia (avec User-Agent approprié)
3. Les extraits sont traités comme des documents normaux par `analyze_historical_documents`
4. Les sources Wikipedia sont taguées dans `sources_citees` avec URL complète
5. Si Wikipedia échoue aussi → retour d'un contexte minimal vide

### Sources de référence

Le skill peut s'appuyer sur :
- **Priorité 1** : Documents fournis par l'utilisateur
- **Priorité 2** : Transcriptions audio (converties en documents textuels)
- **Priorité 3** : Articles Wikipedia (fallback automatique)
- **Jamais** : Connaissances internes du LLM (explicitement interdit par le prompt)

### Niveaux de rigueur

- **Strict** : Rejet de tout terme post-période
- **Modéré** : Accepte termes légèrement anachroniques si accessibilité
- **Souple** : Privilégie compréhension moderne

Le niveau dépend du paramètre `authenticite_vs_accessibilite` de la config.
