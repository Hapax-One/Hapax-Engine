from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    hapax_membership_ids = fields.One2many(
        "hapax.membership",
        "user_id",
        string="Hapax Memberships",
    )
    hapax_membership_count = fields.Integer(compute="_compute_hapax_membership_count")
    hapax_default_project_id = fields.Many2one(
        "hapax.project",
        string="Default Hapax Project",
        check_company=True,
    )

    def _compute_hapax_membership_count(self):
        for user in self:
            user.hapax_membership_count = len(user.hapax_membership_ids)

    def get_hapax_membership(self, project):
        self.ensure_one()
        if not project:
            return self.env["hapax.membership"]
        return self.hapax_membership_ids.filtered(
            lambda membership: membership.project_id == project and membership.status == "active"
        )[:1]

    def has_hapax_admin_access(self, project):
        self.ensure_one()
        if self.has_group("hapax_core.group_hapax_platform_admin"):
            return True
        membership = self.get_hapax_membership(project)
        return bool(membership and membership.has_admin_access())
