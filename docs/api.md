# Initial Hapax API surface

## Public

- `GET /api/v1/health`
- `GET /api/v1/tenant/by-host`
- `GET /api/v1/storefront/vehicles`
- `GET /api/v1/storefront/vehicles/<slug>`
- `POST /api/v1/storefront/availability/quote`

## Customer

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/me`
- `GET /api/v1/me/bookings`
- `POST /api/v1/me/bookings`

## Admin

- `GET /api/v1/admin/dashboard/summary`
- `GET /api/v1/admin/vehicles`
- `POST /api/v1/admin/vehicles`
- `PATCH /api/v1/admin/vehicles/<id>`
- `GET /api/v1/admin/bookings`
- `PATCH /api/v1/admin/bookings/<id>`

## Contract notes

- Tenant resolution is host-driven and server-enforced.
- Frontends should forward `X-Hapax-Tenant-Host` when calling the API from shared app hosts.
- Authentication stays server-side; the browser never receives Odoo service credentials.
- Customer and admin auth both use Hapax-issued session tokens, not direct database access.
- Booking creation is atomic and always happens in a backend service method.
