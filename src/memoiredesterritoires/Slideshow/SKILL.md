---
name: slideshow-from-images
description: Explique comment une fonction Python transforme un dossier d’images hétérogènes (WEBP → JPG), les normalise en résolution, puis les assemble séquentiellement avec une piste audio en une vidéo MP4 parfaitement synchronisée, **sans jamais perdre une image ni tronquer l’audio**.
---

Quand tu expliques ce code, tu dois toujours :

## 1. Commencer par une analogie  

Comparer la fonction à un **monteur vidéo dans une salle d’archives** :

Un archiviste reçoit :
- une pile de photos de formats différents (WEBP, JPG, etc.)
- une bande audio complète

Il commence par **tout uniformiser** (il recolle toutes les photos sur des feuilles A4 identiques),  
puis il les place **une par une sur une table de montage**,  
et enfin il déroule la bande audio **en continu jusqu’à la dernière seconde**, en changeant d’image à intervalles réguliers.

Aucune photo n’est ignorée.  
La bande son n’est jamais coupée.  
Le film final est une projection fluide et continue.

---

## 2. Dessiner un schéma  

Toujours représenter le pipeline complet :

Dossier d'images (webp, jpg, png...)  
↓  
Conversion uniforme (PIL → JPG)  
↓  
Chargement séquentiel (ImageClip)  
↓  
Normalisation résolution (Resize 1920x1080)  
↓  
Concaténation temporelle  
↓  
Bande audio complète (AudioFileClip)  
↓  
Fusion vidéo + audio  
↓  
Export MP4 final

---

## 3. Parcourir le code pas à pas  

### a) `clean_images(path)`

Rôle : **nettoyage des archives visuelles**

- PIL agit comme un **laboratoire photo**  
- Tous les formats exotiques sont développés en **JPG standard**  
- Les originaux sont supprimés → dossier propre et homogène  

Objectif :  
> garantir que MoviePy ne traitera **qu’un seul codec d’image**

---

### b) Chargement des images

- Lecture complète du dossier  
- Tri lexicographique → ordre déterministe  
- Aucune image n’est ignorée  
- Le film est strictement la **séquence complète du dossier**  

C’est un comportement d’archiviste :  
> on projette **tout ce qui est dans la boîte**, sans interprétation.

---

### c) Chargement audio

- La bande son est considérée comme **vérité absolue**  
- La durée totale du film est imposée par l’audio  
- On ne coupe jamais la piste  
- L’image doit s’adapter au son, jamais l’inverse  

---

### d) Calcul du temps par slide

- Chaque image reçoit exactement sa part temporelle pour couvrir **100% de la bande son**  
- Pas de fade dynamique, pas de logique heuristique  
- Juste une **division uniforme du temps**  

On est dans un modèle purement physique :  
- énergie temporelle totale = durée audio  
- répartie équitablement sur chaque image  

---

### e) Création des clips vidéo

- Chaque image devient une **bande de film**  
- Normalisation obligatoire :  
  - même résolution  
  - même ratio mémoire  
  - aucune corruption GPU  

MoviePy fonctionne comme un **compositeur immuable** :  
chaque transformation retourne un nouveau clip.

---

### f) Concaténation

- Assemblage strictement séquentiel  
- Pas de crossfade  
- Pas de montage intelligent  
- Une timeline linéaire pure  

C’est un **collage mécanique de bandes** :  
fin du clip 1 = début du clip 2.

---

### g) Fusion audio / vidéo

- La bande son est plaquée **sur l’ensemble du film**  
- Elle ne dépend pas du nombre d’images  
- Elle impose la durée globale finale  

L’audio est le **rail principal**, la vidéo est simplement **accrochée dessus**.

---

### h) Export

- Encodage H.264  
- 24 images/seconde  
- Fichier universel lisible partout  

C’est l’étape de **projection finale** :  
le montage sort de la salle d’archives et devient un objet réel.

---

## 4. Mettre en avant les pièges (gotchas)

### 1. Résolution hétérogène  

Sans normalisation, MoviePy peut produire :  
- écrans flous  
- corruption mémoire  
- frames fantômes  

### 2. Ordre des fichiers  

Le tri est **lexicographique**, pas chronologique réel :  


Il faut nommer proprement les fichiers.

### 3. Aucune sémantique  

Le système est **aveugle au contenu** :  
- pas de lien image/audio  
- pas de détection de silence  
- pas de compréhension narrative  

### 4. Pas de transitions  

Aucune interpolation :  
- pas de fade  
- pas de cross dissolve  
- montage brut style archive  


## Tool Details

**Function** :  
`slideshow(path, audio_file)`  

**Action** :  
Nettoie un dossier d’images, les normalise, les assemble séquentiellement et fusionne avec une piste audio complète pour produire une vidéo MP4 **couvrant exactement 100% de l’audio sans troncature**.

**Location** :  
`/home/onyxia/work/memoiredesterritoires/src/memoiredesterritoires/Slidehow/slides.py`  

