#!/bin/sh
set -e

# Load .env if present
if [ -f /app/.env ]; then
  echo "[entrypoint] Loading /app/.env"
  set -a
  . /app/.env
  set +a
fi

# --- Persistent volume layout under /app/data ---
echo "[entrypoint] Ensuring data directories..."
mkdir -p \
  /app/data/audio/background_sounds \
  /app/data/audio/archived_audio \
  /app/data/audio_analysis \
  /app/data/generated_speech/archived \
  /app/data/image \
  /app/data/logs \
  /app/data/models \
  /app/data/projects \
  /app/data/scenarios \
  /app/data/sessions \
  /app/data/sound_library

# --- Download Qwen TTS model in the background ---
# Uvicorn starts immediately so health checks pass; TTS endpoint
# returns 503 until the model is ready (checked via READY_FILE).
MODEL_DIR="${QWEN_TTS_LOCAL_DIR:-/app/data/models/qwen3-tts}"
READY_FILE="$MODEL_DIR/.ready"

if [ ! -f "$READY_FILE" ]; then
  echo "[entrypoint] Qwen TTS model not ready – downloading in background..."
  (
    python /app/scripts/download_qwen_tts.py --output-dir "$MODEL_DIR" \
      && touch "$READY_FILE" \
      && echo "[entrypoint] Model download complete – TTS is now available."
  ) &
else
  echo "[entrypoint] Qwen TTS model already present in $MODEL_DIR."
fi

exec "$@"
