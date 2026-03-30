#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${1:-local}"
ENV_FILE="$ROOT_DIR/deploy/env/${ENV_NAME}.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing env file: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

mkdir -p "$ROOT_DIR/deploy/generated"

python3 "$ROOT_DIR/scripts/render_template.py" \
  "$ROOT_DIR/odoo/config/odoo.${ENV_NAME}.conf.template" \
  "$ROOT_DIR/deploy/generated/odoo.${ENV_NAME}.conf"

if [[ "$ENV_NAME" == "staging" ]]; then
  python3 "$ROOT_DIR/scripts/render_template.py" \
    "$ROOT_DIR/deploy/nginx/staging-api.conf.template" \
    "$ROOT_DIR/deploy/generated/staging-api.nginx.conf"
fi
