# Backend setup

## Local development

1. Copy `deploy/env/local.env.example` to `deploy/env/local.env`.
2. Review the defaults for:
   - `ODOO_VERSION`
   - `ODOO_DB_NAME`
   - `POSTGRES_*`
   - `HAPAX_BASE_DOMAIN`
   - `HAPAX_API_COOKIE_DOMAIN`
3. Run:

```bash
./scripts/bootstrap_local.sh
```

This renders the config templates and starts:

- `postgres`
- `odoo`

### Useful commands

```bash
docker compose -f deploy/docker-compose.local.yml --env-file deploy/env/local.env up -d
docker compose -f deploy/docker-compose.local.yml --env-file deploy/env/local.env logs -f odoo
./scripts/odoo_upgrade_modules.sh local hapax_core,hapax_identity,hapax_rental,hapax_api,hapax_portal
```

## Staging deployment

Staging is designed for a DigitalOcean droplet fronted by Nginx and backed by DigitalOcean Managed PostgreSQL.

1. Copy `deploy/env/staging.env.example` to `deploy/env/staging.env`.
2. Set:
   - `ODOO_DB_HOST`
   - `ODOO_DB_PORT`
   - `ODOO_DB_USER`
   - `ODOO_DB_PASSWORD`
   - `ODOO_DB_NAME`
   - `PGSSLMODE=require`
   - `PUBLIC_HOST=staging-api.gohapax.com`
3. Render configs:

```bash
./scripts/render_configs.sh staging
```

4. Start services:

```bash
docker compose -f deploy/docker-compose.staging.yml --env-file deploy/env/staging.env up -d --build
```

5. Upgrade the modules:

```bash
./scripts/odoo_upgrade_modules.sh staging hapax_core,hapax_identity,hapax_rental,hapax_api,hapax_portal
```

## Managed PostgreSQL notes

- Keep the database private to the VPC.
- Require SSL from Odoo with `PGSSLMODE=require`.
- Do not expose `5432` publicly.
- Keep credentials in secret stores only; do not commit env files.
