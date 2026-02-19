# Mémoire des Territoires – Architecture & Product Guide

Mémoire des Territoires orchestre la génération de récits audio historiques à partir d’archives sonores. Le dépôt réunit :

1. **Un backend FastAPI** (`src/server`) qui gère projets, sessions, stockage, chat WebSocket avec le LLM Anthropic, orchestrations Agent 0→3 et synthèse vocale.
2. **Un frontend React/Vite** (`app/`) bilingue FR/EN avec une navigation guidée, un chatbot outillé, drag & drop audio, affichage WaveSurfer et lecteur HTML5.
3. **Un ensemble de skills Python** (`src/memoiredesterritoires/*`) mutualisés entre le chatbot (`main.py`), les automatisations et l’orchestrateur (`orchestrator.py`).

---

## 1. Organisation du dépôt

| Chemin | Description |
| --- | --- |
| `app/` | SPA React (TypeScript, Vite). |
| `src/server/` | App FastAPI (`app.py`, `chat_agent.py`, `automation.py`, etc.). |
| `src/memoiredesterritoires/` | Skills et outils (transcription, mixage, scenario maker…). |
| `main.py` | Entrée CLI pour le chatbot (Anthropic tools + orchestrateur). |
| `config/step_config.json` | Source de vérité pour les étapes UX (titres, skills, automatisations). |
| `data/projects/<nom>/config.json` | Métadonnées consolidées par projet (notes, voix, chemins exports). |
| `data/` | Projets utilisateurs et bibliothèque d’ambiances (`audio/background_sounds`). |
| `Dockerfile`, `makefile` | Tooling multi-plateforme (Mac Apple Silicon + Linux). |

---

## 2. Installation & exécution locale

1. **Variables d’env.**
   ```bash
   cp env.example .env
   # Renseigner : ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL, ELEVENLABS_API_KEY,
   # MAX_AUDIO_MB, VITE_API_BASE (ex: http://localhost:8000)
   ```
2. **Dépendances**
   ```bash
   make install PLATFORM=mac    # ou linux – utilise uv + npm
   ```
3. **API de dev**
   ```bash
   uv run uvicorn server.main:app --reload
   # http://localhost:8000 (Swagger : /docs, front : /web en prod)
   ```
4. **Front de dev**
   ```bash
   cd app && npm run dev        # http://localhost:5173 (proxy vers VITE_API_BASE)
   ```

> Sans clés Anthropic/ELEVENLABS valides, le chatbot et la synthèse vocale retourneront des erreurs 401/400. Vérifiez `.env` et la présence des fichiers `data/projects/<projet>/config.json`.

---

## 3. Makefile & Docker

| Commande | Description |
| --- | --- |
| `make install PLATFORM=<mac|linux>` | Installe Python (via `uv sync`) et npm (`app/`). |
| `make docker-build PLATFORM=<mac|linux>` | Build multi-stage : Node build → `npm run build` → `pip install -e .`. |
| `make docker-run PLATFORM=<mac|linux>` | `docker run --platform linux/arm64 -p 8000:8000 --env-file .env memoire-des-territoires-app`. |
| `make docker-refresh` | Enchaîne install → build → run. |
| `make docker-push GITPAT=<token>` | Login GHCR (`echo $GITPAT | docker login ghcr.io -u julienRactM --password-stdin`), tag/push `ghcr.io/laplateformeio/julienRactM`. |
| `make download-qwen-model` | Télécharge le modèle Qwen3-TTS (via Hugging Face) dans `models/qwen3-tts/` pour une synthèse hors ligne. |

`.dockerignore` élimine `models/`, `notebooks/`, `node_modules/`, les exports audio lourds, etc., pour éviter les contextes > 10 Go.

---

## 4. Parcours produit côté Front

| Étape | Intitulé | Contenu & automatisations |
| --- | --- | --- |
| 1 | **Sélection de projet** | Création / sélection d’un projet. Backend crée `data/projects/<nom>` et initialise `data/projects/<nom>/config.json`. |
| 2 | **Détails du projet** | Brief narratif (FR/EN) envoyé au chatbot. `update_project_notes` + `project_config_builder`. |
| 3 | **Sélection des sources audios** | Upload (validation extension/codecs, taille < `MAX_AUDIO_MB`). Sélection manuelle + suggestions background. Automatisations : transcription → stockage DuckDB, mise à jour de la config projet. |
| 4 | **Consulter les scénarios** | Appel pipeline Agent 0→3 (ScenarioMakerSkill). Progression live (préparation, vérif des sources, génération multi-agents, consolidation). Sélection d’un scénario → synthèse TTS immédiate. |
| 5 | **Modifier le scénario** | Édition manuelle (titre, parties, texte libre). Sauvegarde via API, régénération audio (Qwen3 TTS) accessible sur place, interactions LLM via chat. |
| 6 | **Validation finale** | Double confirmation. Stockage des chemins (texte, audio, voix, background) dans `config.json` du projet. Prêt pour export/diffusion. |

Chaque étape possède son placeholder de chat, son set de skills autorisés et des garde-fous (ex : impossible d’accéder à “Consulter les scénarios” tant qu’aucune piste vocale n’est sélectionnée).

---

## 5. API & endpoints clés

| Méthode | Route | Description |
| --- | --- | --- |
| `POST /projects` | Crée un projet + fichier `data/projects/<nom>/config.json`. |
| `GET /projects` | Liste nom + `scenario_target`. |
| `POST /sessions` | Démarre une session (garde en mémoire scénario cible). |
| `GET/POST /sessions/{id}/step` | Avance ou consulte les métadonnées d’étape. |
| `POST /projects/{name}/audio` | Upload audio (validation `soundfile`). |
| `GET/POST /sessions/{id}/audio-selection` | Pistes voix/ambiances choisies. |
| `GET/POST /background-sounds` | Bibliothèque commune + upload (stocké dans `data/audio/background_sounds/<slug>`). |
| `POST /scenarios/generate` | Déclenche ScenarioMakerSkill + progress tracking. |
| `GET /sessions/{id}/scenarios` | Scénarios générés. |
| `GET/POST /sessions/{id}/scenario-selection` | Scénario retenu (stocké dans session). |
| `GET/POST /sessions/{id}/scenario-audio` | Métadonnées TTS (Qwen) + régénération. |
| `GET /sessions/{id}/scenario-audio/file` | Streaming WAV. |
| `GET /steps` | Définitions front (nombre d’étapes, descriptions, skills). |
| `WS /ws/chat?session_id=…` | Chatbot multi-outils (Anthropic Claude). |

Tous les appels respectent les validations de taille, cohérence projet/session et utilisent `SessionStore` (fichiers JSON dans `settings.session_store`).

---

## 6. Chatbot & orchestrateur

- **`main.py`** définit `TOOLS`, charge les skills complexes (transcription, mixage, scenario maker, etc.) et route les appels du LLM vers les fonctions Python correspondantes (`execute_tool`).
- **`ScenarioMakerSkill`** + **`ScenarioMakerOrchestrator`** (Agent 0→3) orchestrent : extraction configuration, génération structures, rédaction scénarios, timeline audio.
- Le **chat WebSocket** (front) affiche chaque appel d’outil avec ses entrées/sorties pour audit. Les étapes activent/désactivent certains skills (ex : pas de `web_search` à l’étape 1).
- Les **voix** sont définies par projet via `voice_instructions`. Avant de générer le premier audio, pensez à appeler le skill `generate_voice_instructions` ou `edit_voice_instructions` (sinon TTS renvoie 400).

---

## 7. Tableau des skills principaux

| Skill | Objectif | Entrées principales | Tech / module |
| --- | --- | --- | --- |
| `analysis_storage` / `analysis_storage_query` | Stocker / lire transcriptions & analyses dans DuckDB. | `analysis_type`, `source_path`, `result` | DuckDB, Pandas. |
| `transcription` | Chunk + transcription (OpenRouter Gemini). | `path`, `chunk_duration_s`, `model` | `faster-whisper`, OpenRouter. |
| `analysis_storage_background` | Sauvegarder les analyses d’ambiances. | `source_path`, `result` | DuckDB. |
| `background_sounds_description` | Décrire techniquement un bruit (outil, intensité, contexte). | `path`, `context` | Librosa, heuristiques. |
| `background_sound_finder` | Rechercher dans `data/audio/background_sounds`. | `keyword`, `limit` | FS scanning. |
| `adjust_audio_volume` | Appliquer un gain logarithmique, préserver la dynamique. | `input_file`, `volume_percent` | Pydub, Numpy. |
| `mix_voice_with_noise` | Mixer narration + ambiance avec SNR maîtrisé. | `voice_file`, `noise_file`, `snr_db` | Pydub. |
| `insert_background_sounds` | Orchestration SFX ↔ narration. | `voice_file`, `noise_file`, timings | Pydub & outils internes. |
| `text_to_speech_with_instructions` | Synthèse Qwen3 VoiceDesign guidée par instructions projet. | `text`, `project_name`, `language` | `qwen-tts`, Torch, SoundFile. |
| `generate_voice_instructions` | Générer un brief vocal à partir d’un scénario. | `scenario`, `project_name` | Anthropic (LLM). |
| `edit_voice_instructions` | Mettre à jour la voix dans `data/projects/<nom>/config.json`. | `project_name`, `voice_instructions` | JSON helper. |
| `project_config_builder` | Adapter la configuration Agent 0 selon le brief. | `project_description`, `mode` | ScenarioConfigBuilderSkill. |
| `scenario_maker` / `generate_historical_scenario` | Pipeline Agent 0→3 complet (structures, textes, timeline). | `prompt`, `mode`, `config_path` | Orchestrateur. |
| `scenario_ranking` | Évaluer des scénarios vs la config. | `config_path`, `scenarios_dir` | Anthropic. |
| `restricted_web_search` | Recherche web limitée aux domaines autorisés par projet. | `query`, `project_name`, `max_results` | OpenRouter search API. |
| `json_utils.read_json_file` | Lire un JSON (par projet/clé). | `path`, `project_name`, `key` | Helper interne. |
| `update_project_notes` | Persist les notes/brief projet dans `data/projects/<nom>/config.json`. | `description`, `project_name` | JSON helper. |

(Ajoutez vos nouveaux skills dans cette table et documentez-les dans leurs `SKILL.md` respectifs pour que le chatbot les utilise automatiquement.)

---

## 8. Données & configuration

- **`data/projects/<nom>`** : workspace du projet (audio importé, notes, outputs). Nettoyez ce dossier si vous supprimez un projet.
- **`data/audio/background_sounds/*`** : bibliothèque partagée d’ambiances (organisées par dossier). L’API `/background-sounds/upload` slugifie les noms et classe automatiquement les fichiers.
- **`data/projects/<nom>/config.json`** : mis à jour automatiquement lors de la création de projet (voix, notes, allowed_websites). Les skills `update_project_notes`, `generate_voice_instructions`, TTS et validation finale l’enrichissent avec les chemins des fichiers finaux.
- **`.env`** : doit être monté dans Docker (`--env-file .env`). Pour un run autonome côté container, un `docker-entrypoint.sh` lit `/app/.env`.

---

## 9. Tests & dépannage

| Problème | Investigation / Solution |
| --- | --- |
| Chatbot → `No cookie auth credentials found` | Vérifier `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL`. Rebuild/restart le conteneur après mise à jour `.env`. |
| TTS → `voice_instructions missing` | Appeler `generate_voice_instructions` / `edit_voice_instructions` depuis l’étape 5 avant de régénérer l’audio. |
| Build Docker très lent (context > 15 Go) | Contrôler les dossiers non ignorés (`node_modules`, `data/audio` bruts, `models`). Réduire en ajoutant dans `.dockerignore`. |
| `npm run build` échoue | Lancer `cd app && npm run build` en local pour obtenir la stack trace TS complète. |
| Audio upload rejeté | Vérifier l’extension réelle du fichier (`validate_audio_file` compare header vs extension) et la taille (< `MAX_AUDIO_MB`). |
| Chat déconnecté étape 1 | C’est voulu : pas de chatbot sur “Sélection de projet” (UI grisée). Activez-le dès l’étape 2. |

---

## 10. Pistes d’évolution

- Exposer la progression détaillée du pipeline Agent 0→3 (sous-étapes par agent).
- Automatiser la génération des instructions vocales dès la fin de l’étape “Détails du projet”.
- Ajouter des tests d’intégration (pytest + mocks Anthropic) pour sécuriser les endpoints critiques (`/sessions/.../scenario-audio`, `/scenarios/generate`).
- Supporter un export complet (timeline + pistes audio finales) directement depuis la validation finale.

---

La plateforme est prête pour des utilisateurs finaux : navigation guidée, chat outillé, validations de sources audio, génération multi-agents, édition texte/audio avec persistance, et stockage exhaustif des métadonnées projet dans `data/projects/<nom>/config.json`. Utilisez les sections ci-dessus comme référence lors de l’ajout de nouveaux skills, étapes ou intégrations.
