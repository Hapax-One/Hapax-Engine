# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    intellibus_primary_color = fields.Char(
        related="company_id.primary_color",
        readonly=False,
        string="Brand Color",
    )
