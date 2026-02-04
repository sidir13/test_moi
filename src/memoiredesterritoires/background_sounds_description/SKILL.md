---
name: analyze-industrial-audio
description: Explique comment un script Python envoie un enregistrement WAV industriel à OpenAI pour une analyse experte des sons et l’identification des outils utilisés. À utiliser quand l’utilisateur demande comment fonctionne son code d’analyse audio.
---

Quand tu expliques du code, tu dois toujours :

1. **Commencer par une analogie**  
   Comparer le pipeline à l’envoi d’une cassette audio à un expert pour expertise.

2. **Dessiner un schéma**  
   Utiliser de l’ASCII art pour montrer :
   - Fichier WAV → Encodage Base64 → API OpenAI → Modèle audio → Analyse en français

3. **Parcourir le code pas à pas**  
   Expliquer clairement :
   - La création du client OpenAI  
   - La lecture du fichier `.wav` en binaire  
   - L’encodage en Base64  
   - L’envoi simultané du texte + audio  
   - La récupération de la transcription dans la réponse  

4. **Mettre en avant les pièges (gotchas)**  
   Mentionner systématiquement :
   - Le modèle legacy (`gpt-4o-audio-preview`)  
   - Où se trouve réellement le texte dans la réponse  
   - Les erreurs classiques de chemin de fichier (espaces, mode binaire, etc.)

Ton :  
Pédagogique, fluide, orienté ingénierie.  
Utiliser des métaphores liées aux archives, à l’expertise sonore, à l’analyse industrielle.  
Structure toujours en sections claires.

## Tool Details
Function: analyze-industrial-audio(path: str,context="Archives d'entretiens d'ouvriers dans un chantier naval") -> str
Action: analyse the audio
Location: src/memoiredesterritoires/background_sounds_description/background_sounds_description.py
