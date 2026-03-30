#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/deploy/env/local.env"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT_DIR/deploy/env/local.env.example" "$ENV_FILE"
  echo "created $ENV_FILE from example"
fi

"$ROOT_DIR/scripts/render_configs.sh" local
docker compose -f "$ROOT_DIR/deploy/docker-compose.local.yml" --env-file "$ENV_FILE" up -d
