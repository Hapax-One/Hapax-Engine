from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HapaxProject(models.Model):
    _name = "hapax.project"
    _description = "Hapax Project"
    _inherit = ["mail.thread", "hapax.audit.mixin"]
    _order = "name asc, id asc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        tracking=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    slug = fields.Char(required=True, tracking=True)
    primary_host = fields.Char(required=True, tracking=True)
    alias_hosts = fields.Text(
        help="Optional newline-delimited additional hosts for this tenant."
    )
    website_url = fields.Char()
    brand_name = fields.Char()
    brand_color = fields.Char()
    support_email = fields.Char()
    support_phone = fields.Char()
    logo_url = fields.Char()
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("disabled", "Disabled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    metadata_json = fields.Text()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("hapax_project_code_unique", "unique(code)", "The project code must be unique."),
        ("hapax_project_slug_unique", "unique(slug)", "The project slug must be unique."),
        (
            "hapax_project_primary_host_unique",
            "unique(primary_host)",
            "The primary host must be unique.",
        ),
        (
            "hapax_project_company_unique",
            "unique(company_id)",
            "Each company may only own one primary Hapax project.",
        ),
    ]

    @api.constrains("company_id", "slug", "primary_host")
    def _check_company_slug_host(self):
        for record in self:
            if not record.slug or "." in record.slug:
                raise ValidationError("Project slug must be a bare slug without dots.")
            if not record.primary_host or " " in record.primary_host:
                raise ValidationError("Primary host must be a valid hostname.")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            values.setdefault("brand_name", values.get("name"))
        return super().create(vals_list)

    def to_public_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "host": self.primary_host,
            "status": self.status,
            "brandName": self.brand_name or self.name,
            "brandColor": self.brand_color,
            "supportEmail": self.support_email,
            "supportPhone": self.support_phone,
            "logoUrl": self.logo_url,
            "companyId": self.company_id.id,
            "companyName": self.company_id.name,
        }
