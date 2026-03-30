from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    hapax_membership_ids = fields.One2many(
        "hapax.membership",
        "partner_id",
        string="Hapax Memberships",
    )
    hapax_membership_count = fields.Integer(compute="_compute_hapax_membership_count")

    def _compute_hapax_membership_count(self):
        for partner in self:
            partner.hapax_membership_count = len(partner.hapax_membership_ids)

    def action_view_hapax_memberships(self):
        self.ensure_one()
        action = self.env.ref("hapax_identity.action_hapax_memberships").read()[0]
        action["domain"] = [("partner_id", "=", self.id)]
        action["context"] = {"default_partner_id": self.id}
        return action
