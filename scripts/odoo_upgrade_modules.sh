#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${1:-local}"
MODULES="${2:-hapax_core,hapax_identity,hapax_rental,hapax_api,hapax_portal}"
ENV_FILE="$ROOT_DIR/deploy/env/${ENV_NAME}.env"
COMPOSE_FILE="$ROOT_DIR/deploy/docker-compose.${ENV_NAME}.yml"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing env file: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T odoo \
  odoo \
  --db_host="${ODOO_DB_HOST:-db}" \
  --db_port="${ODOO_DB_PORT:-5432}" \
  --db_user="$ODOO_DB_USER" \
  --db_password="$ODOO_DB_PASSWORD" \
  --database="$ODOO_DB_NAME" \
  --update="$MODULES" \
  --stop-after-init
