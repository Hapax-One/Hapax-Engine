import json
import re

from odoo import fields
from odoo.exceptions import AccessDenied, ValidationError
from odoo.http import Controller, Response, request, route


class HapaxApiController(Controller):
    def _json_response(self, payload, status=200):
        body = json.dumps(payload, default=str)
        return Response(
            body,
            status=status,
            content_type="application/json;charset=utf-8",
            headers=[("Cache-Control", "no-store")],
        )

    def _error_response(self, message, status=400, code="bad_request"):
        return self._json_response({"error": {"code": code, "message": message}}, status=status)

    def _handle(self, fn):
        try:
            return self._json_response(fn())
        except ValidationError as exc:
            return self._error_response(str(exc), status=400, code="validation_error")
        except AccessDenied as exc:
            return self._error_response(str(exc) or "Access denied", status=403, code="access_denied")
        except Exception as exc:  # pragma: no cover - keeps API failures legible in staging
            return self._error_response(str(exc), status=500, code="server_error")

    def _request_json(self):
        raw = request.httprequest.get_data(as_text=True) or "{}"
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise ValidationError("Request body must be valid JSON.") from exc

    def _slugify(self, value):
        slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
        return slug or "item"

    def _resolve_project(self, payload=None):
        payload = payload or {}
        host = (
            payload.get("host")
            or request.params.get("host")
            or request.httprequest.headers.get("X-Hapax-Tenant-Host")
            or request.httprequest.headers.get("X-Forwarded-Host")
            or request.httprequest.headers.get("Host")
        )
        project = request.env["hapax.tenant.service"].sudo().resolve_project_for_host(host)
        if not project:
            raise ValidationError("Unable to resolve a Hapax tenant for the requested host.")
        return project

    def _normalize_email(self, value):
        email = (value or "").strip().lower()
        if not email or "@" not in email:
            raise ValidationError("A valid email address is required.")
        return email

    def _get_token(self):
        header = request.httprequest.headers.get("Authorization") or ""
        if header.startswith("Bearer "):
            return header.split(" ", 1)[1].strip()
        return request.httprequest.cookies.get("hapax_portal_session")

    def _portal_session_payload(self, session):
        membership = session.membership_id
        return {
            "tenant": session.project_id.to_public_payload(),
            "session": session.to_public_payload(),
            "user": {
                "id": session.user_id.id,
                "name": session.user_id.name,
                "email": session.user_id.email,
            },
            "membership": membership.to_public_payload() if membership else None,
        }

    def _get_membership(self, user, project):
        membership = request.env["hapax.membership"].sudo().search(
            [
                ("project_id", "=", project.id),
                "|",
                ("user_id", "=", user.id),
                ("partner_id", "=", user.partner_id.id),
            ],
            limit=1,
        )
        if membership and not membership.user_id:
            membership.sudo().write({"user_id": user.id})
        return membership

    def _require_session(self, project=None):
        token = self._get_token()
        session = request.env["hapax.portal.session"].sudo().authenticate_token(token, project=project)
        if not session:
            raise AccessDenied("A valid Hapax session is required.")
        return session

    def _require_admin_session(self, project):
        session = self._require_session(project=project)
        user = session.user_id
        membership = session.membership_id or self._get_membership(user, project)
        if user.has_group("hapax_core.group_hapax_platform_admin"):
            return session
        if membership and membership.has_admin_access():
            return session
        raise AccessDenied("An admin membership is required for this tenant.")

    def _vehicle_values_from_payload(self, project, payload, existing=False):
        values = {}
        field_map = {
            "name": "name",
            "slug": "slug",
            "status": "status",
            "make": "make",
            "model": "model",
            "year": "year",
            "category": "category",
            "summary": "summary",
            "description": "description",
            "transmission": "transmission",
            "fuelType": "fuel_type",
            "seats": "seats",
            "luggageCount": "luggage_count",
            "locationName": "location_name",
            "plateNumber": "plate_number",
            "vin": "vin",
            "imageUrl": "image_url",
            "heroImageUrl": "hero_image_url",
            "gallery": "gallery_json",
            "features": "features_json",
            "dailyRate": "daily_rate",
            "depositAmount": "deposit_amount",
            "minimumDays": "minimum_days",
            "published": "published",
            "rating": "rating",
            "reviewCount": "review_count",
            "metadata": "metadata_json",
        }
        for source_key, field_name in field_map.items():
            if source_key not in payload:
                continue
            value = payload[source_key]
            if field_name in {"gallery_json", "features_json"}:
                value = json.dumps(value or [])
            elif field_name == "metadata_json":
                value = json.dumps(value or {})
            values[field_name] = value

        if not existing:
            values.setdefault("name", payload.get("name"))
            values.setdefault("slug", self._slugify(payload.get("slug") or payload.get("name")))
            values["company_id"] = project.company_id.id
            values["project_id"] = project.id
        elif "slug" in values and not values["slug"]:
            values["slug"] = self._slugify(payload.get("name"))
        return values

    @route("/api/v1/health", type="http", auth="public", methods=["GET"], csrf=False)
    def health(self, **_kwargs):
        return self._json_response({"ok": True, "service": "hapax-api"})

    @route("/api/v1/tenant/by-host", type="http", auth="public", methods=["GET"], csrf=False)
    def tenant_by_host(self, **_kwargs):
        return self._handle(lambda: {"tenant": self._resolve_project().to_public_payload()})

    @route("/api/v1/storefront/vehicles", type="http", auth="public", methods=["GET"], csrf=False)
    def storefront_vehicles(self, **_kwargs):
        def _payload():
            project = self._resolve_project()
            vehicles = request.env["hapax.vehicle"].sudo().search(
                [
                    ("project_id", "=", project.id),
                    ("active", "=", True),
                    ("published", "=", True),
                    ("status", "!=", "inactive"),
                ],
                order="sequence asc, name asc",
            )
            return {
                "tenant": project.to_public_payload(),
                "vehicles": [vehicle.to_storefront_payload() for vehicle in vehicles],
            }

        return self._handle(_payload)

    @route(
        "/api/v1/storefront/vehicles/<string:vehicle_slug>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def storefront_vehicle_detail(self, vehicle_slug, **_kwargs):
        def _payload():
            project = self._resolve_project()
            vehicle = request.env["hapax.vehicle"].sudo().search(
                [
                    ("project_id", "=", project.id),
                    ("slug", "=", vehicle_slug),
                    ("active", "=", True),
                    ("published", "=", True),
                ],
                limit=1,
            )
            if not vehicle:
                raise ValidationError("Vehicle not found for this tenant.")
            return {"tenant": project.to_public_payload(), "vehicle": vehicle.to_storefront_payload()}

        return self._handle(_payload)

    @route(
        "/api/v1/storefront/availability/quote",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def storefront_quote(self, **_kwargs):
        def _payload():
            payload = self._request_json()
            project = self._resolve_project(payload=payload)
            quote = request.env["hapax.rental.service"].sudo().get_quote(
                project,
                payload.get("vehicleId") or payload.get("vehicleSlug"),
                payload.get("dateStart"),
                payload.get("dateEnd"),
            )
            vehicle = quote.pop("vehicle")
            return {"tenant": project.to_public_payload(), "vehicle": vehicle.to_storefront_payload(), "quote": quote}

        return self._handle(_payload)

    @route("/api/v1/auth/register", type="http", auth="public", methods=["POST"], csrf=False)
    def auth_register(self, **_kwargs):
        def _payload():
            payload = self._request_json()
            project = self._resolve_project(payload=payload)
            email = self._normalize_email(payload.get("email"))
            password = payload.get("password") or ""
            if len(password) < 8:
                raise ValidationError("Password must be at least eight characters long.")

            existing_user = request.env["res.users"].sudo().search([("login", "=", email)], limit=1)
            if existing_user:
                raise ValidationError("An account with this email already exists.")

            partner = request.env["res.partner"].sudo().search([("email", "=", email)], limit=1)
            if not partner:
                partner = request.env["res.partner"].sudo().create(
                    {
                        "name": payload.get("name") or email,
                        "email": email,
                        "phone": payload.get("phone"),
                    }
                )

            portal_group = request.env.ref("base.group_portal")
            user = (
                request.env["res.users"]
                .sudo()
                .with_context(no_reset_password=True)
                .create(
                    {
                        "name": payload.get("name") or partner.name or email,
                        "login": email,
                        "email": email,
                        "password": password,
                        "partner_id": partner.id,
                        "company_id": project.company_id.id,
                        "company_ids": [(6, 0, [project.company_id.id])],
                        "group_ids": [(6, 0, [portal_group.id])],
                    }
                )
            )
            if payload.get("phone"):
                partner.sudo().write({"phone": payload.get("phone")})

            membership = request.env["hapax.membership"].sudo().search(
                [("project_id", "=", project.id), ("partner_id", "=", partner.id)],
                limit=1,
            )
            if membership:
                membership.sudo().write({"user_id": user.id, "status": "active"})
            else:
                membership = request.env["hapax.membership"].sudo().create(
                    {
                        "company_id": project.company_id.id,
                        "project_id": project.id,
                        "partner_id": partner.id,
                        "user_id": user.id,
                        "role": "customer",
                        "status": "active",
                        "is_primary": True,
                    }
                )

            session_data = request.env["hapax.portal.session"].sudo().issue_for_user(
                project,
                user,
                membership=membership,
                scope="customer",
                user_agent=request.httprequest.headers.get("User-Agent"),
                ip_address=request.httprequest.remote_addr,
            )
            response = self._portal_session_payload(session_data["record"])
            response["token"] = session_data["token"]
            return response

        return self._handle(_payload)

    @route("/api/v1/auth/login", type="http", auth="public", methods=["POST"], csrf=False)
    def auth_login(self, **_kwargs):
        def _payload():
            payload = self._request_json()
            project = self._resolve_project(payload=payload)
            email = self._normalize_email(payload.get("email"))
            password = payload.get("password") or ""
            if not password:
                raise ValidationError("Password is required.")

            auth_info = request.session.authenticate(
                request.env,
                {
                    "login": email,
                    "password": password,
                    "type": "password",
                },
            )
            uid = auth_info.get("uid")
            if not uid:
                raise AccessDenied("Invalid email or password.")
            user = request.env["res.users"].sudo().browse(uid)
            membership = self._get_membership(user, project)

            if not membership and not user.has_group("hapax_core.group_hapax_platform_admin"):
                raise AccessDenied("This account is not linked to the requested tenant.")

            scope = "admin" if user.has_hapax_admin_access(project) else "customer"
            session_data = request.env["hapax.portal.session"].sudo().issue_for_user(
                project,
                user,
                membership=membership,
                scope=scope,
                user_agent=request.httprequest.headers.get("User-Agent"),
                ip_address=request.httprequest.remote_addr,
            )
            response = self._portal_session_payload(session_data["record"])
            response["token"] = session_data["token"]
            return response

        return self._handle(_payload)

    @route("/api/v1/auth/logout", type="http", auth="public", methods=["POST"], csrf=False)
    def auth_logout(self, **_kwargs):
        def _payload():
            token = self._get_token()
            request.env["hapax.portal.session"].sudo().revoke_token(token)
            return {"ok": True}

        return self._handle(_payload)

    @route("/api/v1/me", type="http", auth="public", methods=["GET"], csrf=False)
    def me(self, **_kwargs):
        def _payload():
            project = self._resolve_project()
            session = self._require_session(project=project)
            return self._portal_session_payload(session)

        return self._handle(_payload)

    @route("/api/v1/me/bookings", type="http", auth="public", methods=["GET"], csrf=False)
    def my_bookings(self, **_kwargs):
        def _payload():
            project = self._resolve_project()
            session = self._require_session(project=project)
            bookings = request.env["hapax.booking"].sudo().search(
                [
                    ("project_id", "=", project.id),
                    ("customer_partner_id", "=", session.partner_id.id),
                ],
                order="date_start desc",
            )
            return {
                "tenant": project.to_public_payload(),
                "bookings": [booking.to_public_payload() for booking in bookings],
            }

        return self._handle(_payload)

    @route("/api/v1/me/bookings", type="http", auth="public", methods=["POST"], csrf=False)
    def create_my_booking(self, **_kwargs):
        def _payload():
            payload = self._request_json()
            project = self._resolve_project(payload=payload)
            session = self._require_session(project=project)
            booking = request.env["hapax.rental.service"].sudo().create_booking(
                project,
                {
                    **payload,
                    "sourceHost": payload.get("sourceHost")
                    or request.httprequest.headers.get("X-Hapax-Tenant-Host")
                    or request.httprequest.headers.get("Host"),
                },
                {
                    "user": session.user_id,
                    "partner": session.partner_id,
                    "membership": session.membership_id,
                },
            )
            return {"tenant": project.to_public_payload(), "booking": booking.to_public_payload()}

        return self._handle(_payload)

    @route("/api/v1/admin/dashboard/summary", type="http", auth="public", methods=["GET"], csrf=False)
    def admin_dashboard_summary(self, **_kwargs):
        def _payload():
            project = self._resolve_project()
            self._require_admin_session(project)

            vehicle_model = request.env["hapax.vehicle"].sudo()
            booking_model = request.env["hapax.booking"].sudo()

            vehicles = vehicle_model.search([("project_id", "=", project.id)], limit=6, order="sequence asc, name asc")
            bookings = booking_model.search([("project_id", "=", project.id)], limit=6, order="create_date desc")
            active_bookings = booking_model.search_count(
                [("project_id", "=", project.id), ("state", "in", ["confirmed", "in_progress"])]
            )
            revenue_total = sum(
                booking_model.search(
                    [
                        ("project_id", "=", project.id),
                        ("state", "in", ["confirmed", "in_progress", "completed"]),
                    ]
                ).mapped("quoted_total")
            )
            return {
                "tenant": project.to_public_payload(),
                "summary": {
                    "vehicleCount": vehicle_model.search_count([("project_id", "=", project.id)]),
                    "activeBookingCount": active_bookings,
                    "availableVehicleCount": vehicle_model.search_count(
                        [("project_id", "=", project.id), ("status", "=", "available")]
                    ),
                    "revenueTotal": float(revenue_total or 0.0),
                },
                "vehicles": [vehicle.to_storefront_payload() for vehicle in vehicles],
                "recentBookings": [booking.to_public_payload() for booking in bookings],
            }

        return self._handle(_payload)

    @route("/api/v1/admin/vehicles", type="http", auth="public", methods=["GET"], csrf=False)
    def admin_vehicles(self, **_kwargs):
        def _payload():
            project = self._resolve_project()
            self._require_admin_session(project)
            vehicles = request.env["hapax.vehicle"].sudo().search(
                [("project_id", "=", project.id)],
                order="sequence asc, name asc",
            )
            return {"tenant": project.to_public_payload(), "vehicles": [vehicle.to_storefront_payload() for vehicle in vehicles]}

        return self._handle(_payload)

    @route("/api/v1/admin/vehicles", type="http", auth="public", methods=["POST"], csrf=False)
    def create_admin_vehicle(self, **_kwargs):
        def _payload():
            payload = self._request_json()
            project = self._resolve_project(payload=payload)
            self._require_admin_session(project)
            values = self._vehicle_values_from_payload(project, payload)
            vehicle = request.env["hapax.vehicle"].sudo().create(values)
            return {"tenant": project.to_public_payload(), "vehicle": vehicle.to_storefront_payload()}

        return self._handle(_payload)

    @route("/api/v1/admin/vehicles/<int:vehicle_id>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def update_admin_vehicle(self, vehicle_id, **_kwargs):
        def _payload():
            payload = self._request_json()
            project = self._resolve_project(payload=payload)
            self._require_admin_session(project)
            vehicle = request.env["hapax.vehicle"].sudo().search(
                [("id", "=", vehicle_id), ("project_id", "=", project.id)],
                limit=1,
            )
            if not vehicle:
                raise ValidationError("Vehicle not found for this tenant.")
            values = self._vehicle_values_from_payload(project, payload, existing=True)
            if values:
                vehicle.sudo().write(values)
            return {"tenant": project.to_public_payload(), "vehicle": vehicle.to_storefront_payload()}

        return self._handle(_payload)

    @route("/api/v1/admin/bookings", type="http", auth="public", methods=["GET"], csrf=False)
    def admin_bookings(self, **_kwargs):
        def _payload():
            project = self._resolve_project()
            self._require_admin_session(project)
            bookings = request.env["hapax.booking"].sudo().search(
                [("project_id", "=", project.id)],
                order="create_date desc",
            )
            return {"tenant": project.to_public_payload(), "bookings": [booking.to_public_payload() for booking in bookings]}

        return self._handle(_payload)

    @route("/api/v1/admin/bookings/<int:booking_id>", type="http", auth="public", methods=["PATCH"], csrf=False)
    def update_admin_booking(self, booking_id, **_kwargs):
        def _payload():
            payload = self._request_json()
            project = self._resolve_project(payload=payload)
            self._require_admin_session(project)
            booking = request.env["hapax.booking"].sudo().search(
                [("id", "=", booking_id), ("project_id", "=", project.id)],
                limit=1,
            )
            if not booking:
                raise ValidationError("Booking not found for this tenant.")

            write_values = {}
            if "notes" in payload:
                write_values["notes"] = payload["notes"]
            if "pickupLocation" in payload:
                write_values["pickup_location"] = payload["pickupLocation"]
            if "returnLocation" in payload:
                write_values["return_location"] = payload["returnLocation"]
            if write_values:
                booking.sudo().write(write_values)

            if payload.get("state") == "cancelled":
                booking.action_cancel()
            elif payload.get("state") == "confirmed":
                booking.action_confirm()
            elif payload.get("state") in {"pending", "in_progress", "completed"}:
                booking.sudo().write({"state": payload["state"]})

            return {"tenant": project.to_public_payload(), "booking": booking.to_public_payload()}

        return self._handle(_payload)
