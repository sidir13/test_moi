# Mémoire des Territoires – App & Skills Documentation

Mémoire des Territoires est désormais une application complète :

- **Backend FastAPI** (`src/server`) qui gère projets, sessions, fichiers audio, automatisations et WebSocket temps réel vers l'orchestrateur Anthropic défini dans `main.py`.
- **Frontend React/Vite** (`app/`) bilingue (FR/EN) avec un pas-à-pas en 6 étapes, un chatbot qui affiche les appels d'outils, et WaveSurfer pour prévisualiser les pistes.
- **Docker** multi-stage qui embarque l'API et le SPA derrière `uvicorn`.

---

## 1. Installation locale

| Étape | Commande | Détails |
| --- | --- | --- |
| Copier la config | `cp env.example .env` | Renseigner `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, `ELEVENLABS_API_KEY`, `MAX_AUDIO_MB`, `VITE_API_BASE`. |
| Installer dépendances | `make install PLATFORM=<linux|mac>` | Utilise `uv sync` pour Python et `npm install` dans `app/`. |
| API dev | `uv run uvicorn server.main:app --reload` | Charge `.env`, expose http://localhost:8000. |
| Front dev | `cd app && npm run dev` | Vite sur http://localhost:5173 (proxy vers API via `VITE_API_BASE`). |

> Sans clés Anthropic/ELEVENLABS, le chatbot retournera un message d'erreur dès qu'il tentera d'appeler les skills.

---

## 2. Docker & déploiement

| Target | Description |
| --- | --- |
| `make docker-build PLATFORM=<linux|mac>` | Build multi-stage : installe Node deps, exécute `npm run build`, puis `pip install -e .` pour aligner sur `pyproject.toml`. |
| `make docker-run PLATFORM=<linux|mac>` | Lance le conteneur (`--env-file .env`) sur le port 8000. `/` sert le SPA, `/health` expose le status API, `/ws/chat` pour le chat. |
| `make docker-refresh` | Chaîne install → build → run (pratique après un pull). |
| `make docker-push GITPAT=<token>` | Login GHCR (`ghcr.io/laplateformeio/julienRactM`), tag et push `latest`. |

`.dockerignore` exclut `models/`, `notebooks/`, `data/audio/*` et `data/audio_analysis/*` afin d'éviter les contextes de build gigantesques.

---

## 3. Parcours applicatif

1. **Sélection de Projet** – création/sélection d'un dossier projet + session backend.
2. **Détails du projet** – saisie du brief narratif, stockage dans `config.json`, déclenchements (`update_project_notes`, etc.).
3. **Sélection des sources audios** – upload des interviews/ambiances (validation codec vs extension + plafond `MAX_AUDIO_MB`). Les skills de transcription/stockage sont invoqués automatiquement.
4. **Consulter les scénarios** – prompts envoyés au pipeline Agent0→3, affichage des automatisations (ranking, voice instructions, TTS...).
5. **Modifier le scénario** – édition texte/audio persistée dans la session avant validation.
6. **Validation finale** – consolidation des chemins audio/transcriptions dans `config.json` et export final.

Le panneau de chat WebSocket réutilise `TOOLS` + `execute_tool` de `main.py`. Chaque appel d'outil apparaît dans l'UI avec ses entrées/sorties, ce qui facilite l'audit.

---

## 4. Table des skills

| Skill | Objectif | Entrées principales | Tech / Module |
| --- | --- | --- | --- |
| `process-number` | Doubler un entier (exemple). | `num` | Python pur – `src/memoiredesterritoires/process_number/process_number.py`. |
| `phone_number` | Normaliser un numéro FR + contexte culturel. | `number` | `phonenumbers` – `phone_number/`. |
| `signature` | Ajouter `yipikayak !` en signature. | — | Template prompt – `signature/`. |
| `adjust-audio-volume` | Gain logarithmique + stats RMS. | `input_file`, `volume_percent` | `pydub`, `numpy` – `adjust_audio_volume.py`. |
| `transcribe_audio` | Chunk + transcription OpenRouter (Gemini). | `path`, `chunk_duration_s`, `model` | `faster-whisper`, OpenRouter – `transcription/transcription.py`. |
| `background_sounds_description` | Décrire un fond sonore industriel. | `path`, `context` | `librosa`, heuristiques – `background_sounds_description.py`. |
| `mix_voice_with_noise` | Mixer narration + ambiance avec SNR cible. | `voice_file`, `noise_file`, `snr_db` | `pydub`, `numpy` – `insert_background_sounds/`. |
| `find-background-sounds` | Lister les ambiances disponibles. | `keyword`, `limit` | FS scan – `background_sound_finder.py`. |
| `save-audio-analysis` | Stocker transcription/analyses dans DuckDB. | `analysis_type`, `source_path`, `result` | `duckdb`, `pandas` – `analysis_storage`. |
| `list-audio-analyses` | Consulter les analyses sauvegardées. | `analysis_type`, `source_path_contains` | `duckdb` – `analysis_storage_query`. |
| `text-to-speech-with-instructions` | Synthèse Qwen3 VoiceDesign selon instructions projet. | `text`, `project_name`, `language` | `qwen-tts`, `torch` – `text_to_speech_with_instructions.py`. |
| `eleven_labs_tts` | Synthèse alternative via ElevenLabs. | `text`, `voice_id` | ElevenLabs REST – `elevenlabs_tts.py`. |
| `edit_voice_instructions` | Modifier `voice_instructions` dans `config.json`. | `project_name`, `voice_instructions` | JSON editing – `voice_instructions/edit_voice_instructions.py`. |
| `generate_voice_instructions` | Générer des instructions vocales via LLM. | `scenario`, `project_name` | Anthropic – `voice_instructions/generate_voice_instructions.py`. |
| `restricted-web-search` | Recherche web limitée aux domaines autorisés. | `query`, `project_name`, `max_results` | OpenRouter search – `web_search/restricted_web_search.py`. |
| `read_json_file` | Lire un JSON local (par projet/clé). | `path`, `project_name`, `key` | Helper – `json_utils/read_json.py`. |
| `update_project_notes` | Sauvegarder le brief projet. | `description`, `project_name` | Helper – `project_notes/update_project_notes.py`. |
| `rank_scenarios_against_config` | Comparer des scénarios au config projet. | `config_path`, `scenarios_dir` | Anthropic – `scenario_ranking/rank_scenarios.py`. |
| `build_project_scenario_config` | Générer une config sur mesure via Agent 0. | `project_description`, `mode` | `ScenarioConfigBuilderSkill` – `project_config_builder`. |
| `generate_historical_scenario` | Pipeline complet Agent0→3 (structures, texte, timeline). | `prompt`, `mode`, `config_path` | `ScenarioMakerSkill` + `orchestrator.py`. |

Ajoutez vos nouvelles entrées dans cette table et mettez à jour les `SKILL.md` associés pour que le chatbot choisisse automatiquement le bon outil.

---

## 5. Configuration & données

- **`config/step_config.json`** : source de vérité pour les étapes UI (titres bilingues, placeholders, skills autorisés, automations post-step).
- **`config.json`** : stocke, par projet, voix, notes, chemins de transcriptions/scénarios/audio final (modifié par plusieurs skills).
- **`data/projects/<nom>`** : workspace créé au moment de la sélection de projet (audio uploadé, notes, sorties). Les anciens dossiers `data/audio/…` restent la bibliothèque partagée.
- **`.env`** : secrets runtime (Anthropic, ElevenLabs, etc.). Doit être présent lors des builds Docker (`--env-file .env`).

---

## 6. Résolution de problèmes

| Symptôme | Résolution |
| --- | --- |
| Chat indique `Missing Anthropic credentials` | Vérifier `ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_BASE_URL` dans `.env` (rebuild/rerun). |
| Build Docker charge >10 GB de contexte | Confirmer que `models/` et `notebooks/` sont bien listés dans `.dockerignore`. |
| Frontend `npm run build` échoue (TS) | Lancer `cd app && npm run build` localement pour voir l'erreur précise avant `make docker-build`. |
| `pip install` échoue dans Docker | Les métadonnées viennent de `pyproject.toml`; vérifier que `build-system` + `packages.find` sont bien renseignés (c'est le cas par défaut). |

---

## 7. Récapitulatif commande

```
make install PLATFORM=linux      # installe les dépendances locales
make docker-build PLATFORM=mac   # build multi-arch (utile sur Apple Silicon)
make docker-run PLATFORM=mac     # lance le conteneur sur http://localhost:8000
make docker-push GITPAT=xxxxx    # push vers ghcr.io/laplateformeio/julienRactM
```

L'ensemble app + orchestrateur est maintenant prêt pour des utilisateurs finaux : navigation par étapes, uploads audio validés, chat outillé, et stockage exhaustif des métadonnées projets. Ajoutez vos nouveaux skills/étapes en mettant à jour `config/step_config.json` et les répertoires `src/memoiredesterritoires/*` pour que tout le produit reste cohérent.
