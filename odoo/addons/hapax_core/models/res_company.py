from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    hapax_slug = fields.Char()
    hapax_primary_host = fields.Char()
    hapax_brand_name = fields.Char()
    hapax_public_email = fields.Char()
    hapax_support_phone = fields.Char()
    hapax_logo_url = fields.Char()
