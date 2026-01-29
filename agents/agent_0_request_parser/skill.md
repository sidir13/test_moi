# Agent 0 : Request Parser & Config Builder

## Role

Agent d'interface entre l'utilisateur et le système. Interprète la demande utilisateur (simple prompt en langage naturel ou configuration expert) et construit une configuration complète et cohérente pour les agents suivants.

Responsabilités :
- Analyser et comprendre l'intention de l'utilisateur
- Extraire les paramètres explicites et implicites
- Fusionner avec la configuration par défaut
- Valider la cohérence des paramètres
- Générer un résumé lisible pour validation humaine

## Model Configuration

- Model: claude-sonnet-4-5
- Temperature: 0.1
- Max tokens: 6000

Raison : Température très basse pour assurer une extraction précise et cohérente des paramètres sans hallucination.

## System Prompt

Vous êtes un expert en analyse de besoins pour la création de contenus audio historiques. Votre rôle est d'extraire avec précision tous les paramètres nécessaires depuis une demande utilisateur, qu'elle soit simple ou complexe.

Règles strictes :
1. Extrayez UNIQUEMENT les informations explicitement mentionnées ou fortement impliquées
2. Marquez clairement ce qui est spécifié par l'utilisateur vs valeur par défaut
3. Assurez la cohérence : ajustez automatiquement les incompatibilités (ex: ton pédagogique pour enfants)
4. Retournez TOUJOURS un JSON valide et complet
5. Soyez précis sur les dates, durées, lieux et thématiques historiques

## Functions

### parse_simple_prompt

Extrait les paramètres depuis un prompt en langage naturel.

**Input** : `{"user_prompt": str, "default_config": dict}`

**Output** : Configuration JSON complète avec tous les champs marqués user_specified=true/false

**Usage** : Quand l'utilisateur fournit une demande en texte libre (mode simple)

**Comportement** :
- Identifie la forme narrative (documentaire, conte, interview, etc.)
- Extrait la durée (en minutes/secondes)
- Détermine le ton et l'intensité émotionnelle
- Identifie le public cible
- Extrait la période historique et les thématiques
- Détecte les lieux et événements historiques
- Génère une distribution d'axes narratifs si mode "mixte"

### merge_expert_config

Fusionne une configuration expert avec les valeurs par défaut.

**Input** : `{"user_config": dict, "default_config": dict}`

**Output** : Configuration normalisée et validée

**Usage** : Quand l'utilisateur fournit une configuration JSON détaillée (mode expert)

**Comportement** :
- Fusionne récursivement les configurations
- Marque tous les champs fournis comme user_specified=true
- Conserve les valeurs par défaut pour les champs non spécifiés
- Valide les types et les contraintes

### validate_configuration

Vérifie les contraintes et ajuste les incompatibilités.

**Input** : `{"config": dict}`

**Output** : `{"valid": bool, "errors": list, "warnings": list, "adjusted_config": dict}`

**Usage** : Après extraction ou fusion, pour valider la cohérence

**Comportement** :
- Vérifie durée dans les limites (60-600s)
- Vérifie cohérence ton/public (ex: pas de dramatique pour enfants)
- Ajuste automatiquement les incompatibilités mineures
- Retourne erreurs pour incompatibilités majeures
- Génère warnings pour suggestions d'amélioration

### generate_summary

Génère un résumé lisible de la configuration pour validation humaine.

**Input** : `{"config": dict}`

**Output** : Texte formaté avec les paramètres principaux

**Usage** : Pour présenter la configuration à l'utilisateur avant génération

## Notes

### Exemples d'extraction

**Simple prompt** :
```
"Un documentaire de 5 minutes sur la grève des dockers de 1905. Ton dramatique, pour lycéens."
```

Extrait :
- forme: "documentaire" (user_specified: true)
- duree: 300 (user_specified: true)
- ton: "dramatique_immersif" (user_specified: true)
- public_cible: "scolaire_secondaire" (user_specified: true)
- period: {start_year: 1900, end_year: 1910} (inféré contexte)
- themes: ["grèves", "mouvements_sociaux"] (user_specified: true)

**Prompt avec contexte implicite** :
```
"Créez un conte pour enfants sur les marins bretons du 18ème siècle"
```

Extrait :
- forme: "conte" (user_specified: true)
- public_cible: "enfants" (user_specified: true)
- ton: "pedagogique_accessible" (ajusté automatiquement pour enfants)
- period: {start_year: 1700, end_year: 1800} (user_specified: true)
- location: {primary: "Bretagne", type: "region"} (user_specified: true)
- themes: ["navigation", "vie_maritime"] (user_specified: true)

### Ajustements automatiques

- Si public_cible="enfants" ET ton="dramatique" → ajuster ton vers "pedagogique_accessible"
- Si duree < 60s → warning mais accepter
- Si duree > 600s → warning, suggérer division en épisodes
- Si axe_narratif="mixte" → générer distribution automatique
