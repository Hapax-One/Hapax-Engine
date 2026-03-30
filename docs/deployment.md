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
   - seed the first tenant with `scripts/seed_staging_tenant.sh staging`
   - module upgrades succeed
   - `GET /api/v1/tenant/by-host`
   - `GET /api/v1/storefront/vehicles`
   - `POST /api/v1/storefront/availability/quote`
5. Connect `staging-api.gohapax.com`.
6. Point the frontend staging deployment at `staging-api.gohapax.com`.
7. Promote the backend first, then the frontend.

If the registrar or DNS cutover is blocked, add a temporary validation hostname to `PUBLIC_HOSTS` such as
`staging-api.<droplet-ip>.sslip.io`, render configs again, and provision a real Let's Encrypt certificate for that host.
This keeps preview and staging traffic on trusted HTTPS without weakening TLS verification.

## Nginx responsibilities

- terminate TLS
- proxy `/websocket` and `/longpolling` to Odoo realtime
- proxy `/api/v1/*` and `/web*` to Odoo HTTP
- preserve `Host`, `X-Forwarded-*`, and `X-Forwarded-Proto`

## Safety rules

- Never point preview frontend builds at production Odoo.
- Never expose the managed Postgres instance publicly.
- Keep production `gohapax.com` on the current combined stack until the split stack is validated.
- If DNS is managed outside DigitalOcean, treat A-record cutover as a separate step after staging API verification.

## Staging seed data

1. Copy `deploy/env/staging.seed.env.example` to `deploy/env/staging.seed.env`.
2. Set private admin and customer credentials in that seed env file.
3. Run `scripts/seed_staging_tenant.sh staging` on the staging host or from the checked-out repo on the droplet.
4. Verify tenant resolution with the frontend tenant host in `X-Hapax-Tenant-Host`, even before public DNS is cut over.
5. For Vercel preview deployments, set `HAPAX_TENANT_HOST_OVERRIDE` and `NEXT_PUBLIC_HAPAX_TENANT_HOST_OVERRIDE`
   to the seeded tenant host so preview domains can resolve the correct tenant while cookies still stay bound to the
   real preview hostname.
