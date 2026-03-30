# Deployment runbook

## Environments

- `local`: Docker compose with local Postgres
- `staging`: Docker compose on a DigitalOcean droplet with Managed PostgreSQL
- `production`: same topology as staging after validation

## Staging-first rollout

1. Snapshot the current production stack before changes.
2. Provision staging infrastructure.
3. Deploy `hapax-engine` to staging.
4. Validate:
   - Odoo boots
   - module upgrades succeed
   - `GET /api/v1/tenant/by-host`
   - `GET /api/v1/storefront/vehicles`
   - `POST /api/v1/storefront/availability/quote`
5. Connect `staging-api.gohapax.com`.
6. Point the frontend staging deployment at `staging-api.gohapax.com`.
7. Promote the backend first, then the frontend.

## Nginx responsibilities

- terminate TLS
- proxy `/websocket` and `/longpolling` to Odoo realtime
- proxy `/api/v1/*` and `/web*` to Odoo HTTP
- preserve `Host`, `X-Forwarded-*`, and `X-Forwarded-Proto`

## Safety rules

- Never point preview frontend builds at production Odoo.
- Never expose the managed Postgres instance publicly.
- Keep production `gohapax.com` on the current combined stack until the split stack is validated.
