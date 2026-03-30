from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HapaxMembership(models.Model):
    _name = "hapax.membership"
    _description = "Hapax Membership"
    _inherit = ["mail.thread", "hapax.audit.mixin"]
    _order = "company_id asc, role desc, id desc"
    _rec_name = "display_name"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company",
        required=True,
        tracking=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    project_id = fields.Many2one(
        "hapax.project",
        required=True,
        tracking=True,
        index=True,
        check_company=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        tracking=True,
        index=True,
        ondelete="cascade",
    )
    user_id = fields.Many2one(
        "res.users",
        tracking=True,
        index=True,
        check_company=True,
        ondelete="set null",
    )
    email = fields.Char(related="partner_id.email", store=True, readonly=False)
    phone = fields.Char(related="partner_id.phone", store=True, readonly=False)
    role = fields.Selection(
        [
            ("customer", "Customer"),
            ("member", "Member"),
            ("admin", "Admin"),
            ("owner", "Owner"),
        ],
        required=True,
        default="customer",
        tracking=True,
    )
    status = fields.Selection(
        [
            ("invited", "Invited"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("revoked", "Revoked"),
        ],
        required=True,
        default="active",
        tracking=True,
    )
    is_primary = fields.Boolean(default=False, tracking=True)
    joined_at = fields.Datetime(default=lambda self: fields.Datetime.now(), tracking=True)
    notes = fields.Text()
    display_name = fields.Char(compute="_compute_display_name", store=True)

    _sql_constraints = [
        (
            "hapax_membership_project_partner_unique",
            "unique(project_id, partner_id)",
            "A partner may only have one membership per project.",
        ),
        (
            "hapax_membership_project_user_unique",
            "unique(project_id, user_id)",
            "A user may only have one membership per project.",
        ),
    ]

    @api.depends("project_id.name", "partner_id.name", "role")
    def _compute_display_name(self):
        for record in self:
            partner_name = record.partner_id.name or record.email or "Member"
            project_name = record.project_id.name or "Hapax"
            record.display_name = f"{partner_name} · {project_name} ({record.role})"

    @api.constrains("company_id", "project_id")
    def _check_project_company(self):
        for record in self:
            if record.project_id and record.project_id.company_id != record.company_id:
                raise ValidationError("Membership company must match the project company.")

    @api.constrains("user_id", "partner_id")
    def _check_user_partner(self):
        for record in self:
            if record.user_id and record.user_id.partner_id != record.partner_id:
                raise ValidationError("Membership user must match the linked contact.")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            project_id = values.get("project_id")
            if project_id and not values.get("company_id"):
                project = self.env["hapax.project"].browse(project_id)
                values["company_id"] = project.company_id.id
        return super().create(vals_list)

    def has_admin_access(self):
        self.ensure_one()
        return self.role in {"admin", "owner"} and self.status == "active"

    def to_public_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "role": self.role,
            "status": self.status,
            "projectId": self.project_id.id,
            "projectSlug": self.project_id.slug,
            "companyId": self.company_id.id,
            "isPrimary": self.is_primary,
        }
