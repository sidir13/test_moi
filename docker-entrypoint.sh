#!/bin/sh
set -e
if [ -f /app/.env ]; then
  echo "[entrypoint] Loading /app/.env"
  set -a
  . /app/.env
  set +a
fi
exec "$@"
