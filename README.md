# Hapax Engine

`hapax-engine` is the split Odoo backend foundation for `gohapax.com`.

It owns:

- the Odoo 19 runtime and deployment assets
- tenant-aware platform modules
- the first Hapax identity, rental, and API surfaces
- staging and production deployment scaffolding for DigitalOcean

The existing root-level starter files are still present for reference while this repo is being normalized. The active platform foundation now lives under `odoo/`, `deploy/`, `scripts/`, and `docs/`.

## Target architecture

- Odoo 19 on DigitalOcean
- one PostgreSQL database per environment
- one Odoo database with multi-company tenancy
- one `res.company` per tenant
- shared identity through `res.partner`, `res.users`, and `hapax.membership`
- custom controller surface at `api.gohapax.com`
- backend-only booking creation and availability enforcement

## Repository layout

```text
hapax-engine/
├── deploy/
│   ├── docker-compose.local.yml
│   ├── docker-compose.staging.yml
│   ├── env/
│   └── nginx/
├── docs/
│   ├── api.md
│   ├── deployment.md
│   ├── setup.md
│   ├── tenant-model.md
│   └── what-codex-changed.md
├── odoo/
│   ├── addons/
│   │   ├── hapax_api/
│   │   ├── hapax_core/
│   │   ├── hapax_identity/
│   │   ├── hapax_portal/
│   │   └── hapax_rental/
│   └── config/
├── scripts/
└── .github/workflows/
```

## Quick start

1. Copy `deploy/env/local.env.example` to `deploy/env/local.env`.
2. Run `./scripts/bootstrap_local.sh`.
3. Open `http://localhost:8069` for Odoo.
4. Install the Hapax modules in this order:
   - `hapax_core`
   - `hapax_identity`
   - `hapax_rental`
   - `hapax_api`
   - `hapax_portal`

## Main docs

- [Local and staging setup](/Users/nicholassalmon/Hapax-Engine/docs/setup.md)
- [Deployment runbook](/Users/nicholassalmon/Hapax-Engine/docs/deployment.md)
- [Tenant model](/Users/nicholassalmon/Hapax-Engine/docs/tenant-model.md)
- [Initial API surface](/Users/nicholassalmon/Hapax-Engine/docs/api.md)
- [Codex change log](/Users/nicholassalmon/Hapax-Engine/docs/what-codex-changed.md)
