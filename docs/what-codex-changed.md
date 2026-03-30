# What Codex changed

This file tracks the split backend foundation work for the `gohapax.com` platform build.

## Foundation

- introduced a structured Odoo backend layout under `odoo/`, `deploy/`, `scripts/`, and `docs/`
- added local and staging deployment templates for Odoo 19
- added first-party Hapax addon namespaces for core, identity, rental, API, and portal flows
- documented the split deployment and tenant model

## Implemented modules

- `hapax_core`
  - tenant/project model, config params, host resolution service, and platform groups
- `hapax_identity`
  - shared memberships between contacts, users, tenants, and companies
- `hapax_rental`
  - vehicles, rate plans, availability blocks, bookings, and atomic booking service logic
- `hapax_portal`
  - API session tokens for shared customer/admin auth
- `hapax_api`
  - public storefront, auth, customer, and admin endpoints under `/api/v1/*`

## Validation

- Python syntax validation passes for the new backend addons and scripts via `python3 -m compileall`
- Added an Odoo `TransactionCase` for the rental quote service under `hapax_rental/tests/test_rental_service.py`

## Infra note

- Production state was snapshotted from `64.225.54.5` before any change
- DigitalOcean and Vercel control planes are not currently authenticated in this local/browser environment, so staging resource inspection/provisioning is still blocked outside the repos

## Follow-up

Update this file after each implementation milestone with:

- module and API changes
- infrastructure changes
- validation notes
- remaining gaps
