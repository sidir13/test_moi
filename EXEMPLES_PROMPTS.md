# 📝 Exemples de Prompts

Exemples de prompts à utiliser avec le système pour générer des archives sonores historiques.

## Mode Test Local (Ollama)

### Utilisation Interactive

```bash
python main_local.py
```

Le système vous demandera d'entrer votre prompt. Exemples à tester :

### Utilisation Directe

```bash
# Prompt simple
python main_local.py "Un documentaire de 3 minutes sur une grève de dockers en 1905"

# Événement historique
python main_local.py "Racontez la bataille de Verdun en 1916, durée 5 minutes"

# Vie quotidienne
python main_local.py "La vie dans les mines de charbon au début du 20ème siècle, 4 minutes"

# Patrimoine industriel
python main_local.py "L'histoire des chantiers navals, période 1900-1950, 6 minutes"

# Événement local
python main_local.py "Une grève ouvrière dans une usine textile en 1936, ambiance tendue, 3 minutes"
```

## Prompts par Catégorie

### 🏭 Patrimoine Industriel

```bash
# Chantiers navals
python main_local.py "L'activité des chantiers navals au début du 20ème siècle, sons de construction, 5 minutes"

# Usines textiles
python main_local.py "Une journée dans une filature en 1920, bruits de machines, 4 minutes"

# Aciéries
python main_local.py "Le travail dans une aciérie en 1930, chaleur et bruit des forges, 5 minutes"

# Mines
python main_local.py "Descente dans la mine de charbon, période 1900-1920, ambiance oppressante, 6 minutes"
```

### ⚔️ Événements Historiques

```bash
# Grande Guerre
python main_local.py "Les tranchées de Verdun en 1916, témoignage de poilu, 5 minutes"

# Résistance
python main_local.py "La résistance pendant l'Occupation, 1940-1944, ton sobre, 6 minutes"

# Libération
python main_local.py "La libération d'une ville en août 1944, joie et chaos, 4 minutes"

# Entre-deux-guerres
python main_local.py "Les années folles dans un café parisien, ambiance jazz, 5 minutes"
```

### 🏘️ Vie Quotidienne

```bash
# Quartiers populaires
python main_local.py "La vie dans un quartier ouvrier en 1930, sons de rue, 4 minutes"

# Marchés
python main_local.py "Un marché de quartier dans les années 1920, ambiance vivante, 3 minutes"

# Écoles
python main_local.py "Une journée à l'école communale en 1910, discipline et apprentissage, 5 minutes"

# Fêtes populaires
python main_local.py "Une fête de village dans les années 1930, musique et danses, 4 minutes"
```

### 📢 Mouvements Sociaux

```bash
# Grèves
python main_local.py "Une grève générale en 1936, manifestations et revendications, 5 minutes"

# Syndicats
python main_local.py "La naissance d'un syndicat ouvrier en 1920, espoir et luttes, 6 minutes"

# Mai 1968
python main_local.py "Les événements de Mai 1968, barricades et slogans, 5 minutes"

# Front populaire
python main_local.py "Les congés payés de 1936, joie des premiers départs en vacances, 4 minutes"
```

### 🌾 Monde Rural

```bash
# Agriculture
python main_local.py "Les moissons à la main dans les années 1920, travail collectif, 5 minutes"

# Artisanat
python main_local.py "Un forgeron de village en 1910, sons du travail du métal, 4 minutes"

# Foires
python main_local.py "Une foire aux bestiaux dans les années 1930, ambiance campagnarde, 3 minutes"

# Exode rural
python main_local.py "Le départ vers la ville dans les années 1950, nostalgie et espoir, 5 minutes"
```

### 🚢 Maritime et Portuaire

```bash
# Ports
python main_local.py "Un port de commerce en 1900, déchargement de navires, 5 minutes"

# Pêche
python main_local.py "Le retour des bateaux de pêche à l'aube, criée aux poissons, 4 minutes"

# Navigation
python main_local.py "La traversée de l'Atlantique en paquebot, années 1920, 6 minutes"

# Dockers
python main_local.py "Le travail des dockers dans un port en 1930, dur labeur, 5 minutes"
```

### 🎭 Culture et Loisirs

```bash
# Cafés concerts
python main_local.py "Un café-concert parisien en 1900, chansons et ambiance, 5 minutes"

# Cinéma muet
python main_local.py "Une projection de cinéma muet en 1920, piano d'accompagnement, 4 minutes"

# Bals populaires
python main_local.py "Un bal musette dans les années 1930, accordéon et danse, 5 minutes"

# Guinguettes
python main_local.py "Une guinguette au bord de l'eau en 1925, rires et chansons, 4 minutes"
```

## Structure des Prompts

### Format Recommandé

```
[Sujet] + [Période] + [Durée] + [Ambiance/Ton] (optionnel)
```

### Exemples Détaillés

```bash
# Minimal
python main_local.py "Grève de 1936, 3 minutes"

# Standard
python main_local.py "Une grève ouvrière en 1936, ambiance tendue, 4 minutes"

# Détaillé
python main_local.py "Une grève générale dans une usine automobile en 1936, tensions sociales, espoir de victoire, sons de manifestation, 5 minutes"

# Très détaillé
python main_local.py "Documentaire sur la grande grève de 1936 dans les usines Renault, occupation d'usine, négociations syndicales, victoire du Front Populaire, ambiance à la fois tendue et joyeuse, avec sons d'usine, chants ouvriers et discours, durée 6 minutes"
```

## Éléments Optionnels à Ajouter

### Lieu Spécifique

```bash
python main_local.py "La grève des dockers à Marseille en 1950, 4 minutes"
```

### Personnage Principal

```bash
python main_local.py "Le témoignage d'un mineur de fond dans le Nord en 1920, 5 minutes"
```

### Ambiance Sonore

```bash
python main_local.py "L'usine en 1930, avec bruits de machines à vapeur et sifflets, 4 minutes"
```

### Ton Narratif

```bash
python main_local.py "La libération de Paris en août 1944, ton épique et émouvant, 6 minutes"
```

### Multiple Perspectives

```bash
python main_local.py "La grève de 1947 vue par un ouvrier, un patron et un syndicaliste, 7 minutes"
```

## Conseils pour de Bons Prompts

### ✅ Bons Prompts

- Spécifient une période historique claire
- Indiquent une durée cible (3-10 minutes recommandé)
- Mentionnent le contexte ou l'ambiance souhaité
- Sont suffisamment détaillés mais pas trop complexes

### ❌ Prompts à Éviter

- Trop vagues : "Histoire de France"
- Trop longs : plus de 15 minutes pour les tests
- Anachroniques : "Les ouvriers avec leurs smartphones en 1920"
- Trop complexes : plusieurs périodes et lieux différents

## Prompt pour Tester les Limites

```bash
# Test court (1-2 minutes)
python main_local.py "Un bref moment dans une usine en 1920, 90 secondes"

# Test long (10 minutes)
python main_local.py "Histoire complète de la grève de 1936, de ses origines à ses conséquences, 10 minutes"

# Test sans durée (le système décide)
python main_local.py "Une journée de docker au port en 1930"

# Test multi-lieux
python main_local.py "Trois scènes de la Résistance : le maquis, la ville, la ferme, 6 minutes"

# Test ambiance complexe
python main_local.py "La libération : joie, chaos, vengeance et espoir mêlés, août 1944, 7 minutes"
```

## Production avec Claude

Pour passer en production avec l'API Claude (meilleure qualité) :

```bash
# Configurer .env avec votre clé API
echo "ANTHROPIC_API_KEY=sk-ant-votre-clé" > .env

# Utiliser le CLI principal
python cli.py generate "Votre prompt ici"

# Avec options
python cli.py generate "Votre prompt" --mode simple --output-dir output/prod
```

---

**💡 Astuce** : Commencez avec des prompts simples de 3-4 minutes pour tester, puis augmentez progressivement la complexité !
