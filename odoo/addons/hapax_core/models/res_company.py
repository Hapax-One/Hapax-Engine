from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    hapax_slug = fields.Char()
    hapax_primary_host = fields.Char()
    hapax_brand_name = fields.Char()
    hapax_brand_color = fields.Char()
    hapax_public_email = fields.Char()
    hapax_support_phone = fields.Char()
    hapax_logo_url = fields.Char()
    hapax_logo_image = fields.Image(attachment=True, max_width=1024, max_height=1024)
    hapax_banner_image = fields.Image(attachment=True, max_width=2560, max_height=1440)
