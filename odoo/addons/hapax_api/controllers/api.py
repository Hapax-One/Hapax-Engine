import base64
import binascii
import json
import re

from odoo import fields
from odoo.exceptions import AccessDenied, ValidationError
from odoo.http import Controller, Response, request, route


class HapaxApiController(Controller):
    def _tenant_service(self):
        return request.env["hapax.tenant.service"].sudo()

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

    def _public_base_url(self):
        forwarded_proto = request.httprequest.headers.get("X-Forwarded-Proto")
        forwarded_host = request.httprequest.headers.get("X-Forwarded-Host")
        host = forwarded_host or request.httprequest.headers.get("Host")
        scheme = forwarded_proto or request.httprequest.scheme or "https"
        if host:
            return f"{scheme}://{host}".rstrip("/")
        return request.httprequest.url_root.rstrip("/")

    def _tenant_payload(self, project):
        return project.to_public_payload(base_url=self._public_base_url())

    def _load_project_metadata(self, project):
        try:
            return json.loads(project.metadata_json or "{}")
        except ValueError:
            return {}

    def _project_settings_payload(self, project):
        metadata = self._load_project_metadata(project)
        onboarding = {
            "setupStep": metadata.get("setup_step") or "business-details",
            "setupCompleted": bool(metadata.get("setup_completed")),
        }
        return {
            "tenant": self._tenant_payload(project),
            "project": {
                "id": project.id,
                "name": project.name,
                "code": project.code,
                "slug": project.slug,
                "primaryHost": project.primary_host,
                "websiteUrl": project.website_url,
                "brandName": project.brand_name or project.name,
                "brandColor": project.brand_color,
                "supportEmail": project.support_email,
                "supportPhone": project.support_phone,
                "logoUrl": project._asset_url("logo_image", self._public_base_url()) or project.logo_url,
                "bannerUrl": project._asset_url("banner_image", self._public_base_url()),
                "companyId": project.company_id.id,
                "companyName": project.company_id.name,
                "setupStep": onboarding["setupStep"],
                "setupCompleted": onboarding["setupCompleted"],
                "metadata": metadata,
            },
            "onboarding": onboarding,
            "baseDomain": self._tenant_service().get_base_domain(),
        }

    def _project_values_from_payload(self, project, payload):
        values = {}

        if "name" in payload:
            name = (payload.get("name") or "").strip()
            if not name:
                raise ValidationError("Business name is required.")
            values["name"] = name

        if "brandName" in payload:
            brand_name = (payload.get("brandName") or "").strip()
            if not brand_name:
                raise ValidationError("Business display name is required.")
            values["brand_name"] = brand_name

        if "supportEmail" in payload:
            support_email = (payload.get("supportEmail") or "").strip()
            values["support_email"] = self._normalize_email(support_email) if support_email else False

        if "supportPhone" in payload:
            values["support_phone"] = (payload.get("supportPhone") or "").strip() or False

        if "brandColor" in payload:
            brand_color = (payload.get("brandColor") or "").strip()
            if brand_color and not re.match(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", brand_color):
                raise ValidationError("Choose a valid brand color.")
            values["brand_color"] = brand_color or False

        if "logoUrl" in payload:
            values["logo_url"] = (payload.get("logoUrl") or "").strip() or False

        if "logoImageData" in payload:
            values["logo_image"] = self._parse_image_payload(payload.get("logoImageData"), "logo")
            if values["logo_image"]:
                values["logo_url"] = False

        if "bannerImageData" in payload:
            values["banner_image"] = self._parse_image_payload(payload.get("bannerImageData"), "banner")

        tenant_service = self._tenant_service()
        next_slug = None
        if "slug" in payload:
            next_slug = self._slugify(payload.get("slug"))
            values["slug"] = next_slug

        if "primaryHost" in payload or "host" in payload:
            host_value = payload.get("primaryHost") or payload.get("host")
            next_host = tenant_service.sanitize_host(host_value)
            if not next_host:
                raise ValidationError("A valid hostname is required.")
            values["primary_host"] = next_host
        elif next_slug:
            values["primary_host"] = f"{next_slug}.{tenant_service.get_base_domain()}"

        if "websiteUrl" in payload:
            website_url = (payload.get("websiteUrl") or "").strip()
            values["website_url"] = website_url or False
        elif values.get("primary_host"):
            values["website_url"] = f"https://{values['primary_host']}"

        metadata = self._load_project_metadata(project)
        metadata_updated = False
        for field_name, metadata_key in {
            "industry": "industry",
            "businessType": "business_type",
            "businessAddress": "business_address",
            "secondaryPhone": "secondary_phone",
            "whatsappNumber": "whatsapp_number",
            "timeZone": "time_zone",
        }.items():
            if field_name not in payload:
                continue
            metadata[metadata_key] = (payload.get(field_name) or "").strip()
            metadata_updated = True

        if "contactEmail" in payload:
            contact_email = self._normalize_email(payload.get("contactEmail")) if payload.get("contactEmail") else False
            values["support_email"] = contact_email
            metadata["contact_email"] = contact_email or ""
            metadata_updated = True

        if "phoneNumber" in payload:
            phone_number = (payload.get("phoneNumber") or "").strip()
            values["support_phone"] = phone_number or False
            metadata["phone_number"] = phone_number
            metadata_updated = True

        if "hours" in payload:
            metadata["business_hours"] = payload.get("hours") or []
            metadata_updated = True

        if "payoutDetails" in payload:
            metadata["payout_details"] = payload.get("payoutDetails") or {}
            metadata_updated = True

        if "inviteMembers" in payload:
            metadata["invite_members"] = payload.get("inviteMembers") or []
            metadata_updated = True

        if "setupStep" in payload:
            metadata["setup_step"] = (payload.get("setupStep") or "").strip() or "business-details"
            metadata_updated = True

        if "setupCompleted" in payload:
            metadata["setup_completed"] = bool(payload.get("setupCompleted"))
            metadata_updated = True

        if metadata_updated:
            values["metadata_json"] = json.dumps(metadata)

        return values

    def _parse_image_payload(self, value, label):
        if not value:
            return False

        raw = (value or "").strip()
        match = re.match(
            r"^data:(image/(png|jpeg|jpg|webp));base64,(?P<data>[A-Za-z0-9+/=\s]+)$",
            raw,
            re.IGNORECASE,
        )
        if not match:
            raise ValidationError(f"Upload a PNG, JPG, or WEBP {label} image.")

        encoded = re.sub(r"\s+", "", match.group("data"))
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValidationError(f"The {label} image could not be decoded.") from exc

        if len(decoded) > 4 * 1024 * 1024:
            raise ValidationError(f"The {label} image must be 4 MB or smaller.")

        return encoded

    def _sync_company_with_project(self, project):
        self._tenant_service().sync_company_from_project(project)
        metadata = self._load_project_metadata(project)
        company_partner = project.company_id.partner_id.sudo()
        company_values = {}
        if metadata.get("business_address") is not None:
            company_values["street"] = metadata.get("business_address") or False
        if project.support_email:
            company_values["email"] = project.support_email
        if project.support_phone:
            company_values["phone"] = project.support_phone
        if company_values:
            company_partner.write(company_values)

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
            "tenant": self._tenant_payload(session.project_id),
            "session": session.to_public_payload(),
            "user": {
                "id": session.user_id.id,
                "name": session.user_id.name,
                "email": session.user_id.email,
            },
            "membership": membership.to_public_payload() if membership else None,
        }

    def _session_response(self, project, user, membership=False, scope=False, include_project=False):
        project.ensure_one()
        user.ensure_one()
        resolved_scope = scope or ("admin" if user.has_hapax_admin_access(project) else "customer")
        session_data = request.env["hapax.portal.session"].sudo().issue_for_user(
            project,
            user,
            membership=membership,
            scope=resolved_scope,
            user_agent=request.httprequest.headers.get("User-Agent"),
            ip_address=request.httprequest.remote_addr,
        )
        response = self._portal_session_payload(session_data["record"])
        response["token"] = session_data["token"]
        if include_project:
            settings = self._project_settings_payload(project)
            response["project"] = settings["project"]
            response["onboarding"] = settings["onboarding"]
        return response

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
        return self._handle(lambda: {"tenant": self._tenant_payload(self._resolve_project())})

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
                "tenant": self._tenant_payload(project),
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
            return {"tenant": self._tenant_payload(project), "vehicle": vehicle.to_storefront_payload()}

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
            return {"tenant": self._tenant_payload(project), "vehicle": vehicle.to_storefront_payload(), "quote": quote}

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

            return self._session_response(project, user, membership=membership, scope="customer")

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
            return self._session_response(project, user, membership=membership, scope=scope)

        return self._handle(_payload)

    @route("/api/v1/business/auth/register", type="http", auth="public", methods=["POST"], csrf=False)
    def business_auth_register(self, **_kwargs):
        def _payload():
            payload = self._request_json()
            tenant = self._tenant_service().bootstrap_business_tenant(
                name=payload.get("name"),
                email=payload.get("email"),
                password=payload.get("password"),
                phone=payload.get("phone"),
            )
            return self._session_response(
                tenant["project"],
                tenant["user"],
                membership=tenant["membership"],
                scope="admin",
                include_project=True,
            )

        return self._handle(_payload)

    @route("/api/v1/business/auth/login", type="http", auth="public", methods=["POST"], csrf=False)
    def business_auth_login(self, **_kwargs):
        def _payload():
            payload = self._request_json()
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
            requested_host = (
                payload.get("host")
                or request.httprequest.headers.get("X-Hapax-Tenant-Host")
                or request.httprequest.headers.get("X-Forwarded-Host")
                or request.httprequest.headers.get("Host")
            )
            project = self._tenant_service().find_business_project_for_user(user, requested_host=requested_host)
            if not project:
                raise AccessDenied("This account is not linked to a Hapax business org.")

            membership = self._get_membership(user, project)
            if not user.has_group("hapax_core.group_hapax_platform_admin") and not (
                membership and membership.has_admin_access()
            ):
                raise AccessDenied("This account does not have business admin access.")

            return self._session_response(project, user, membership=membership, scope="admin", include_project=True)

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
                "tenant": self._tenant_payload(project),
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
            return {"tenant": self._tenant_payload(project), "booking": booking.to_public_payload()}

        return self._handle(_payload)

    @route("/api/v1/admin/project", type="http", auth="public", methods=["GET"], csrf=False)
    def admin_project(self, **_kwargs):
        def _payload():
            project = self._resolve_project()
            self._require_admin_session(project)
            return self._project_settings_payload(project)

        return self._handle(_payload)

    @route("/api/v1/admin/project", type="http", auth="public", methods=["PATCH"], csrf=False)
    def update_admin_project(self, **_kwargs):
        def _payload():
            payload = self._request_json()
            project = self._resolve_project(payload=payload)
            self._require_admin_session(project)
            values = self._project_values_from_payload(project, payload)
            if values:
                project.sudo().write(values)
                self._sync_company_with_project(project)
            return self._project_settings_payload(project)

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
                "tenant": self._tenant_payload(project),
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
            return {"tenant": self._tenant_payload(project), "vehicles": [vehicle.to_storefront_payload() for vehicle in vehicles]}

        return self._handle(_payload)

    @route("/api/v1/admin/vehicles", type="http", auth="public", methods=["POST"], csrf=False)
    def create_admin_vehicle(self, **_kwargs):
        def _payload():
            payload = self._request_json()
            project = self._resolve_project(payload=payload)
            self._require_admin_session(project)
            values = self._vehicle_values_from_payload(project, payload)
            vehicle = request.env["hapax.vehicle"].sudo().create(values)
            return {"tenant": self._tenant_payload(project), "vehicle": vehicle.to_storefront_payload()}

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
            return {"tenant": self._tenant_payload(project), "vehicle": vehicle.to_storefront_payload()}

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
            return {"tenant": self._tenant_payload(project), "bookings": [booking.to_public_payload() for booking in bookings]}

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

            return {"tenant": self._tenant_payload(project), "booking": booking.to_public_payload()}

        return self._handle(_payload)
