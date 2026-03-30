#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${1:-staging}"
ENV_FILE="${HAPAX_ENV_FILE:-$ROOT_DIR/deploy/env/${ENV_NAME}.env}"
SEED_ENV_FILE="${HAPAX_SEED_ENV_FILE:-$ROOT_DIR/deploy/env/${ENV_NAME}.seed.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing env file: $ENV_FILE" >&2
  exit 1
fi

if [[ ! -f "$SEED_ENV_FILE" ]]; then
  echo "missing seed env file: $SEED_ENV_FILE" >&2
  echo "copy deploy/env/${ENV_NAME}.seed.env.example to deploy/env/${ENV_NAME}.seed.env and fill in credentials" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$SEED_ENV_FILE"
set +a

docker compose \
  --env-file "$ENV_FILE" \
  -f "$ROOT_DIR/deploy/docker-compose.${ENV_NAME}.yml" \
  exec -T \
  -e HAPAX_STAGING_ADMIN_EMAIL \
  -e HAPAX_STAGING_ADMIN_PASSWORD \
  -e HAPAX_STAGING_CUSTOMER_EMAIL \
  -e HAPAX_STAGING_CUSTOMER_PASSWORD \
  -e HAPAX_BASE_DOMAIN \
  -e HAPAX_API_COOKIE_DOMAIN \
  -e HAPAX_SEED_PROJECT_SLUG \
  -e HAPAX_SEED_PROJECT_NAME \
  -e HAPAX_SEED_PROJECT_CODE \
  -e HAPAX_SEED_PRIMARY_HOST \
  -e HAPAX_SEED_ALIAS_HOSTS \
  -e HAPAX_SEED_WEBSITE_URL \
  -e HAPAX_SEED_BRAND_NAME \
  -e HAPAX_SEED_BRAND_COLOR \
  -e HAPAX_SEED_SUPPORT_EMAIL \
  -e HAPAX_SEED_SUPPORT_PHONE \
  odoo sh -lc \
  'odoo shell --db_host="$HOST" --db_port="$PORT" --db_user="$USER" --db_password="$PASSWORD" -d "'"${ODOO_DB_NAME}"'"' \
  < "$ROOT_DIR/scripts/seed_staging_tenant.py"
