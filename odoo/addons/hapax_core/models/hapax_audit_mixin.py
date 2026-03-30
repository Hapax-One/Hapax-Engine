from odoo import fields, models


class HapaxAuditMixin(models.AbstractModel):
    _name = "hapax.audit.mixin"
    _description = "Hapax Audit Mixin"

    source_system = fields.Char()
    external_ref = fields.Char(index=True)
    integration_payload = fields.Text()
    last_synced_at = fields.Datetime()
