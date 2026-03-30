from urllib.parse import urlparse

from odoo import api, models


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
