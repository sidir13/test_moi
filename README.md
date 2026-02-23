# Mémoire des Territoires – Architecture, Pipeline & Ops Guide

Mémoire des Territoires assemble des récits audio immersifs à partir d’archives sonores. Le dépôt combine :

1. **Un backend FastAPI** (`src/server/`) qui orchestre projets, sessions, stockage audio/vidéo, WebSocket chat et toutes les automatisations (Agents 0→3, TTS Qwen, mixage, slideshow).
2. **Un frontend React/Vite** (`app/`) bilingue, structuré autour de six étapes avec un copilote LLM outillé (sélection audio, sourcing, édition, validation).
3. **Une librairie de skills Python** (`src/memoiredesterritoires/*`) factorisée entre le chatbot CLI (`main.py`), l’orchestrateur multi-agent (`orchestrator.py`) et les automations backend.

---

## 1. Tour du dépôt

| Chemin | Description |
| --- | --- |
| `app/` | SPA React (TypeScript, Vite, TanStack Query, Zustand). |
| `src/server/app.py` | Entrée FastAPI : routes REST/WS, chargement config, automation runner, TTS, slideshow. |
| `src/server/chat_agent.py` | Proxy Anthropic (Claude) + mapping outils → skills Python. |
| `src/server/automation.py` | Gestion des automations par étape (`step_config.json`). |
| `src/server/session_store.py` | Persistence file-based des sessions (JSON) et suivi de progression. |
| `src/memoiredesterritoires/` | Skills (transcription OpenRouter, background planner, scenario maker, TTS, mixage…). Chaque dossier possède un `SKILL.md`. |
| `main.py` | Interface CLI interactive pour piloter les skills hors UI. |
| `config/default_config.json` | Baseline Agent 0 (génération paramètres, tons, publics, durées, etc.). |
| `config/step_config.json` | Source de vérité des étapes (nom, description, skills autorisés, automations). |
| `data/projects/<nom>/` | Espace projet (config consolidée, uploads audio, notes, exports finaux). |
| `data/audio/background_sounds/` | Bibliothèque partagée d’ambiances. |
| `models/qwen3-tts/` | Modèle Qwen3 TTS (optionnel hors-ligne). |
| `makefile`, `Dockerfile`, `docker-entrypoint.sh` | Tooling multi-plateforme (uv + npm + multi-stage build). |

---

## 2. Installation & exécution locale

1. **Variables d’environnement**
   ```bash
   cp env.example .env
   # Renseigner :
   #  - ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL
   #  - OPENROUTER_API_KEY (si transcription)
   #  - ELEVENLABS_API_KEY (optionnel)
   #  - MAX_AUDIO_MB (valeur par défaut 500)
   #  - VITE_API_BASE (http://localhost:8000 en dev)
   #  - SCENARIO_DEFAULT_CONFIG (optionnel pour override de config agent)
   ```

2. **Dépendances**
   ```bash
   make install PLATFORM=mac        # ou PLATFORM=linux
   # -> uv sync (backend) + npm install (frontend)
   ```

3. **Back uniquement**
   ```bash
   uv run uvicorn server.app:create_app --factory --reload
   # http://127.0.0.1:8000  (Swagger: /docs, Health: /health)
   ```

4. **Front uniquement**
   ```bash
   cd app && npm run dev            # http://127.0.0.1:5173
   # Vite utilise VITE_API_BASE comme proxy API
   ```

5. **Build complet (prod-like)**
   ```bash
   make run-app                     # uv sync + npm install + npm run build + uvicorn
   ```

> La synthèse vocale et la génération de scénarios exigent des clés Anthropic/Qwen valides. Sans `voice_instructions` définies pour un projet, la route `/sessions/{id}/scenario-audio` refusera la génération (400).

---

## 3. Makefile & Docker

| Commande | Description |
| --- | --- |
| `make install PLATFORM=<mac|linux>` | Installe dépendances Python (uv) + front (npm). |
| `make run-app` | Étapes enchaînées : `uv sync` → `npm install --legacy-peer-deps` → `npm run build` → `uv run uvicorn server.app:create_app --factory --reload`. |
| `make docker-build PLATFORM=<mac|linux>` | Build multi-stage (Node build + uv). Résout Apple Silicon (`--platform linux/arm64`). |
| `make docker-run PLATFORM=<mac|linux>` | Lance le container avec `--env-file .env -p 8000:8000`. |
| `make docker-refresh-<mac|linux>` | Rebuild + run en un seul raccourci. |
| `make docker-push GITPAT=<token>` | Push de l’image sur GHCR (`ghcr.io/laplateformeio/julienRactM`). |
| `make download-qwen-model` | Télécharge `Qwen3TTSModel` pour exécuter le TTS hors connexion. |

`.dockerignore` ignore les gros artefacts (`data/audio`, `models`, `node_modules`, exports) pour éviter des contextes > 10 Go.

---

## 4. Parcours produit & UX

| # | Vue | Détails UI + automations |
| --- | --- | --- |
| 1 | **Sélection de Projet** | Crée/charge un projet. Backend initialise `data/projects/<nom>/` (sous-dossiers `audio/`, `notes/`, `outputs/`). Le chat est désactivé à cette étape. |
| 2 | **Détails du projet** | Brief narratif + nouveaux champs optionnels : contexte, public cible (select sur la base `config/default_config.json`), ton narratif, consignes vocales (avec traduction auto côté skill), durée cible (slider 30 s–10 min). `advanceStep` sauvegarde tout et déclenche `update_project_notes` + `project_config_builder`. |
| 3 | **Sélection des sources audios** | Uploads `.wav/.mp3` (validation extension/taux, conversion possible via pydub). Sélection de 1 voix + jusqu’à 2 ambiances. Automations : transcription (OpenRouter), stockage DuckDB, inventaire des backgrounds. |
| 4 | **Consulter les scénarios** | Lancement ScenarioMakerSkill (Agents 0→3). Progress UI en 4 jalons (préparation → contrôles audio → génération → consolidation). Résultats classés (ranking LLM). On peut écouter chaque pitch (TTS) et afficher le “sourcing” (mapping phrase → segments transcription). |
| 5 | **Modifier le scénario** | Édition du scénario retenu (titres, contenu, sourcing). Régénération audio (Qwen) et diaporama (MoviePy) via boutons dédiés. Les audios mixés sont stockés dans `data/projects/<nom>/outputs/audio_<slug>.wav`, le slideshow dans `video_<slug>.mp4`. |
| 6 | **Validation finale** | Copie des assets générés vers le dossier `outputs/`, écriture des métadonnées (`final_scenario`, `final_audio`, `final_slideshow`, `finalized_at`) dans la config projet. Raccourcis pour télécharger audio/vidéo. |

Chaque étape active un sous-ensemble de skills côté chatbot (cf. `config/step_config.json`) et met à jour l’état `useSessionStore` (scénarios prêts, audio prêt, scenarioEdited, etc.). Les projets finalisés conservent l’accès aux vues 4/5 pour itérations ultérieures.

---

## 5. Backend & API principales

### Routes REST

| Méthode | Route | Description |
| --- | --- | --- |
| `POST /projects` | Crée un projet, initialise le dossier et `config.json`. |
| `GET /projects` | Liste des projets (nom, scénario cible, statuts audio/vidéo). |
| `GET /projects/{name}` | Renvoie le profil projet (notes, voix, ton/public/durée, préférences par défaut, scénarios, assets finaux). |
| `POST /sessions` | Démarre une session liée à un projet (stockée dans `data/sessions/*.json`). |
| `POST /sessions/{id}/step` | Avance une étape (`project_details`, `audio_sources`, etc.) → déclenche automations. |
| `GET/POST /projects/{name}/audio` | Upload/énumère les pistes déposées. |
| `GET/POST /sessions/{id}/audio-selection` | Sauvegarde la sélection de voix/ambiances pour la session. |
| `POST /background-sounds/upload` | Ajoute une ambiance partagée (slug automatique, stockage dans `data/audio/background_sounds`). |
| `GET /background-sounds` | Recherche par mot-clé. |
| `POST /scenarios/generate` | Lance ScenarioMakerSkill. Suivi via `GET /sessions/{id}/scenario-progress`. |
| `GET/POST /sessions/{id}/scenario-selection` | Choisit / consulte le scénario retenu. |
| `GET/POST /sessions/{id}/scenario-audio` | Génère ou renvoie le dernier TTS (métadonnées + chemin). |
| `GET /sessions/{id}/scenario-audio/file` | Streaming WAV (range requests supportées). |
| `POST /sessions/{id}/slideshow` | Génère le MP4 (images + audio). |
| `GET /sessions/{id}/slideshow/file` | Télécharge le MP4 généré. |
| `GET /steps` | Liste des étapes (libellés FR/EN, skills, automations). |
| `GET /health` | Status minimal pour le LB. |

### WebSocket

`/ws/chat?session_id=...` ouvre une session Anthropic multi-outils. Chaque réponse peut contenir une liste d’invocations (par ex. transcription, mixage, scenario_maker). Les résultats sont renvoyés au front (diff apparition) et loggés dans `data/sessions/<session>.json`.

### Logs clés

- `SCENARIO_STAGE` : progression Agent pipeline.
- `SCENARIO_AUDIO_START` / `_DONE` / `_FAILED` : génération TTS.
- `SCENARIO_SLIDESHOW_START` : timeline video.
- `Project preferences updated` : audit des champs ton/public/durée/voice quand un utilisateur valide “Détails du projet”.
- `Voice instructions missing` : fallback auto (extraction du brief) si aucune consigne n’est fournie.

Les logs incluent session/project pour faciliter le débogage multi-utilisateur.

---

## 6. Skills catalogue (résumé)

| Skill | Rôle | Paramètres principaux | Notes |
| --- | --- | --- | --- |
| `analysis_storage` / `analysis_storage_query` | Sauvegarder / requêter les analyses (DuckDB). | `analysis_type`, `source_path`, `result`. | Utilisé après transcription ou description SFX. |
| `transcription` | Découpe WAV → envoie sur OpenRouter → reconstitue transcription. | `path`, `chunk_duration_s`, `model`. | Couverture totale du fichier (pas de troncature). |
| `background_sound_finder` | Liste les ambiances dispo. | `keyword`, `limit`. | Explore `data/audio/background_sounds`. |
| `background_sounds_description` | Analyse acoustique rapide + tags. | `path`, `context`. | Sert à guider l’agent audio. |
| `mix_voice_with_noise` | Mix voix + ambiance (SNR contrôlé). | `voice_file`, `noise_file`, `snr_db`, `start_time`. | Construit par pydub. |
| `insert_background_sounds` | Orchestration ab initio des backgrounds (LLM plan). | `voice_file`, `noise_file`, `plan`. | Utilise un plan généré par Claude (max 2 ambiances). |
| `adjust_audio_volume` | Ajuste le gain global d’un wav. | `input_file`, `volume_percent`. | Rapporte RMS avant/après. |
| `project_config_builder` | Fusionne le brief utilisateur avec `default_config`. | `project_description`, `mode`. | Agent 0 complet. |
| `scenario_maker` | Agents 0→3 (structure, scénario, timeline). | `prompt`, `mode`, `config_path`. | Produit JSON + fichiers sous `output/`. |
| `scenario_ranking` | Re-classe les scénarios par pertinence. | `config_path`, `scenarios_dir`. | Écrit `scenario_ranking` dans la config. |
| `generate_voice_instructions` | Rédige un prompt vocal en anglais. | `project_name`, `scenario_text`. | Utilise `VOICE_TRANSLATION_MODEL`. |
| `edit_voice_instructions` | Sauvegarde une consigne vocale personnalisée. | `project_name`, `voice_instructions`. | Écrit dans `data/projects/<nom>/config.json`. |
| `text_to_speech_with_instructions` | Synthèse Qwen3 (voix + backgrounds planifiés). | `text`, `project_name`, `language`. | Lit `voice_instructions`, applique plan d’ambiances (5–10 s, jamais chevauchées). |
| `slideshow` | Convertit N images → vidéo MP4 + audio. | `image_dir`, `audio_file`, `output_path`. | Normalise les images (PIL) et respecte 100 % de la durée audio. |
| `restricted_web_search` | Recherche web limitée aux domaines autorisés. | `query`, `project_name`, `max_results`. | Exploite OpenRouter search plugin. |
| `json_utils.read_json_file` | Lit un JSON local (option project/clé). | `path`, `project_name`, `key`. | Utilisé par le chatbot pour inspection de config. |

Chaque skill dispose d’un `SKILL.md` décrivant la procédure à suivre par le LLM.

---

## 7. Données & configuration projet

- **`data/projects/<nom>/config.json`** centralise : notes, ton/public/durée, instructions vocales, allowed_websites, ranking, scénarios, timelines, chemins d’exports (`outputs/audio_<slug>.wav`, `outputs/video_<slug>.mp4`), dernier état de session. Intègre aussi le `scenario_config` complet utilisé lors de la dernière génération.
- **`data/projects/<nom>/audio/`** : fichiers uploadés (voix ou ambiances dédiées).
- **`data/projects/<nom>/outputs/`** : assets finalisés (audio mixé, audio voix-only, slideshow).
- **`data/sessions/*.json`** : snapshots d’étapes + appels de skills (utile pour audit). Nettoyables sans perdre les projets.
- **`data/audio/background_sounds/`** : bibliothèque partagée accessible par tous les projets. Le nommage (`slug/filename.wav`) suit le formulaire d’upload.
- **Variables clés** :
  - `MAX_AUDIO_MB` : taille max d’upload (convertie en bytes).
  - `BACKGROUND_PLAN_MODEL` : modèle utilisé pour planifier l’insertion de bruitages.
  - `VOICE_TRANSLATION_MODEL` : LLM qui traduit les consignes vocales.
  - `SCENARIO_DEFAULT_CONFIG` : fichier bascule pour les options ton/public/durée dans le front.

---

## 8. Tests, QA & dépannage

| Symptôme | Pistes |
| --- | --- |
| `ModuleNotFoundError: AutoProcessor` lors de `make run-app` | Vérifiez que `transformers>=4.57` est dans l’environnement uv (cf. `uv pip freeze`). Refaire `uv sync`. |
| TTS régénéré malgré un audio existant | L’UI impose désormais un check d’audio avant `valider l’édition`. Assurez-vous que `final_audio.path` existe dans la config avant de quitter l’étape. |
| Slideshow 500 : `TypeError: slideshow() takes 2 positional arguments but 3 were given` | Copier la version récente de `slides.py` (signature `(image_dir, audio_file, output_path)`). |
| Ambiances jouées en continu | Le background planner place désormais 2 segments max, 5–10 s chacun, jamais superposés. Si vous voyez encore un mix complet, videz `data/projects/<nom>/outputs` et régénérez. |
| Champs public/ton/durée non persistés | Les logs `Project preferences updated` n’apparaissent pas → vérifier que l’étape “Détails du projet” a bien envoyé les valeurs (front `advanceStep`). |
| Upload audio rejeté (`invalid audio file`) | Le validateur lit l’entête WAV/MP3 (pydub). Re-encoder en PCM 16/24 bits via `ffmpeg -i input.wav -acodec pcm_s16le output.wav`. |
| Autoplay vidéo = muet | L’UI désactive l’autoplay et expose un bouton Play → le son est actif dès la lecture manuelle. |

Tests unitaires ciblent les agents (`tests/test_agent_0.py`) et le session store (`tests/test_session_store.py`). Ajoutez vos scénarios dans `tests/` et exécutez `uv run pytest`.

---

## 9. Évolutions possibles

1. **Historique des scénarios** : conserver toutes les générations (pas seulement la dernière) avec diff textuel & audio.
2. **Éditeur audio avancé** : ajuster visuellement l’insertion des backgrounds (drag/drop sur la timeline).
3. **Export complet** : packaging ZIP (script + audio + slideshow + sourcing JSON).
4. **Monitoring** : brancher Prometheus/OpenTelemetry sur les évènements `SCENARIO_*` et temps d’appel des skills (transcription, TTS).
5. **Automations récurrentes** : planifier la régénération automatique pour des séries (“scénario du jour”) via le moteur d’automations existant.

---

## 10. Références rapides

- **UI** : `app/src/views/ProjectDetailsView.tsx` pour les nouveaux champs, `app/src/components/*` pour les lecteurs audio/vidéo.
- **Persistences** : `project_store.py` (settings + audio selection), `automation_runner._apply_project_preferences` (ton/public/durée/voice).
- **TTS** : `src/memoiredesterritoires/text_to_speech_with_instructions/text_to_speech_with_instructions.py` (planification des backgrounds, atténuation -8 dB, insertion non chevauchée).
- **Slideshow** : `src/memoiredesterritoires/Slideshow/slides.py` (PIL + MoviePy), API route `/sessions/{id}/slideshow`.
- **Scenario Maker** : Agents décrits en détail dans `AGENTS.md` (Request Parser, Structure Architect, Scenario Writer, Audio Production Engineer).

La plateforme est prête pour une exploitation multi-projets : chaque workspace est isolé dans `data/projects/<nom>`, toutes les instructions sont versionnées, les voix sont paramétrables, les ambiances sont gérées par planification intelligente, et l’utilisateur peut revenir modifier ou régénérer à tout moment. Utilisez ce guide comme référence pour toute contribution (nouveau skill, nouvelle étape, intégration API ou amélioration UX). Bonnes archives ! 
