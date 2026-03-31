import json
import re
from urllib.parse import urlparse

from odoo import api, models
from odoo.exceptions import ValidationError


class HapaxTenantService(models.AbstractModel):
    _name = "hapax.tenant.service"
    _description = "Hapax Tenant Service"

    @api.model
    def get_base_domain(self):
        return (
            self.env["ir.config_parameter"].sudo().get_param("hapax.base_domain")
            or "gohapax.com"
        ).strip()

    @api.model
    def get_cookie_domain(self):
        return (
            self.env["ir.config_parameter"].sudo().get_param("hapax.api_cookie_domain")
            or ".gohapax.com"
        ).strip()

    @api.model
    def sanitize_host(self, host):
        raw = (host or "").strip()
        if not raw:
            return ""
        if "://" in raw:
            raw = urlparse(raw).netloc or raw
        raw = raw.split("/")[0].split(":")[0].strip().lower()
        return raw

    @api.model
    def slugify(self, value):
        slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
        return slug or "tenant"

    @api.model
    def ensure_unique_slug(self, value, exclude_project=False):
        base_slug = self.slugify(value)
        slug = base_slug
        counter = 2
        project_model = self.env["hapax.project"].sudo()

        while True:
            domain = [("slug", "=", slug)]
            if exclude_project:
                domain.append(("id", "!=", exclude_project.id))
            if not project_model.search_count(domain):
                return slug
            slug = f"{base_slug}-{counter}"
            counter += 1

    @api.model
    def build_host_for_slug(self, slug):
        return f"{slug}.{self.get_base_domain()}"

    @api.model
    def ensure_unique_project_code(self, value):
        base_code = re.sub(r"[^A-Z0-9]+", "", (value or "").upper())[:8] or "HAPAX"
        code = f"HX-{base_code}"
        counter = 2
        project_model = self.env["hapax.project"].sudo()

        while project_model.search_count([("code", "=", code)]):
            suffix = f"{counter:02d}"
            trimmed = base_code[: max(1, 8 - len(suffix))]
            code = f"HX-{trimmed}{suffix}"
            counter += 1
        return code

    @api.model
    def sync_company_from_project(self, project):
        project.ensure_one()
        company = project.company_id.sudo()
        company.write(
            {
                "name": project.name,
                "hapax_slug": project.slug,
                "hapax_primary_host": project.primary_host,
                "hapax_brand_name": project.brand_name or project.name,
                "hapax_public_email": project.support_email or False,
                "hapax_support_phone": project.support_phone or False,
                "hapax_logo_url": project.logo_url or False,
            }
        )

        if company.partner_id:
            company.partner_id.sudo().write(
                {
                    "name": project.brand_name or project.name,
                    "email": project.support_email or False,
                    "phone": project.support_phone or False,
                    "website": project.website_url or False,
                }
            )

    @api.model
    def find_business_project_for_user(self, user, requested_host=None):
        user.ensure_one()
        requested_project = self.resolve_project_for_host(requested_host) if requested_host else self.env["hapax.project"]
        if requested_project and user.has_hapax_admin_access(requested_project):
            return requested_project

        if user.hapax_default_project_id and user.has_hapax_admin_access(user.hapax_default_project_id):
            return user.hapax_default_project_id

        membership = self.env["hapax.membership"].sudo().search(
            [
                ("user_id", "=", user.id),
                ("status", "=", "active"),
                ("role", "in", ["admin", "owner"]),
            ],
            order="is_primary desc, joined_at asc, id asc",
            limit=1,
        )
        if membership:
            if not user.hapax_default_project_id:
                user.sudo().write({"hapax_default_project_id": membership.project_id.id})
            return membership.project_id
        return self.env["hapax.project"]

    @api.model
    def bootstrap_business_tenant(self, *, name, email, password, phone=False):
        email = (email or "").strip().lower()
        if not email or "@" not in email:
            raise ValidationError("A valid email address is required.")
        if len(password or "") < 8:
            raise ValidationError("Password must be at least eight characters long.")

        user_model = self.env["res.users"].sudo()
        if user_model.search([("login", "=", email)], limit=1):
            raise ValidationError("An account with this email already exists.")

        company_name = (name or "").strip() or email.split("@", 1)[0]
        partner_model = self.env["res.partner"].sudo()
        partner = partner_model.search([("email", "=", email)], limit=1)
        if not partner:
            partner = partner_model.create(
                {
                    "name": company_name,
                    "email": email,
                    "phone": phone or False,
                }
            )
        elif phone:
            partner.write({"phone": phone})

        slug = self.ensure_unique_slug(company_name or email.split("@", 1)[0])
        primary_host = self.build_host_for_slug(slug)
        company = self.env["res.company"].sudo().create({"name": company_name})
        project = self.env["hapax.project"].sudo().create(
            {
                "name": company_name,
                "code": self.ensure_unique_project_code(slug),
                "company_id": company.id,
                "slug": slug,
                "primary_host": primary_host,
                "website_url": f"https://{primary_host}",
                "brand_name": company_name,
                "brand_color": "#5145E5",
                "support_email": email,
                "support_phone": phone or False,
                "status": "active",
                "metadata_json": json.dumps(
                    {
                        "setup_step": "business-details",
                        "setup_completed": False,
                    }
                ),
            }
        )

        tenant_admin_group = self.env.ref("hapax_core.group_hapax_tenant_admin")
        user = (
            user_model.with_context(no_reset_password=True)
            .create(
                {
                    "name": company_name,
                    "login": email,
                    "email": email,
                    "password": password,
                    "partner_id": partner.id,
                    "company_id": company.id,
                    "company_ids": [(6, 0, [company.id])],
                    "hapax_default_project_id": project.id,
                    # Business owners are internal tenant admins, not portal-only users.
                    "group_ids": [(6, 0, [tenant_admin_group.id])],
                }
            )
        )

        membership = self.env["hapax.membership"].sudo().create(
            {
                "company_id": company.id,
                "project_id": project.id,
                "partner_id": partner.id,
                "user_id": user.id,
                "role": "owner",
                "status": "active",
                "is_primary": True,
            }
        )

        self.sync_company_from_project(project)
        return {
            "company": company,
            "project": project,
            "partner": partner,
            "user": user,
            "membership": membership,
        }

    @api.model
    def resolve_project_for_host(self, host):
        clean_host = self.sanitize_host(host)
        if not clean_host:
            return self.env["hapax.project"]

        project = self.env["hapax.project"].sudo().search(
            [
                ("active", "=", True),
                ("status", "=", "active"),
                ("primary_host", "=", clean_host),
            ],
            limit=1,
        )
        if project:
            return project

        candidates = self.env["hapax.project"].sudo().search(
            [("active", "=", True), ("status", "=", "active")]
        )
        return candidates.filtered(
            lambda project_row: clean_host
            in [line.strip().lower() for line in (project_row.alias_hosts or "").splitlines() if line.strip()]
        )[:1]
