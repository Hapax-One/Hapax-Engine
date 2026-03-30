# Tenant model

## Core rules

- `res.company` is the tenant isolation boundary.
- `hapax.project` maps the public tenant host and brand metadata to a company.
- `hapax.membership` connects a user and partner to a project, company, and role.

## Shared records

These may be global with `company_id = False` when appropriate:

- shared identity metadata
- countries
- currencies
- reference taxonomies

## Tenant-scoped records

These must always carry a concrete `company_id`:

- vehicles
- bookings
- availability blocks
- rate plans
- operational dashboard metrics

## Implementation rules

- required `company_id`
- `_check_company_auto = True`
- `check_company=True` on relational fields
- record rules based on the current user's company access
- service-layer validation in addition to record rules
