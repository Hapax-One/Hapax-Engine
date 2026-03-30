from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    hapax_base_domain = fields.Char(
        string="Hapax base domain",
        config_parameter="hapax.base_domain",
    )
    hapax_api_cookie_domain = fields.Char(
        string="Hapax API cookie domain",
        config_parameter="hapax.api_cookie_domain",
    )
