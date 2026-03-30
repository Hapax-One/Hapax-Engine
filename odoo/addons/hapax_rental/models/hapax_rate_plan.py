from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HapaxRatePlan(models.Model):
    _name = "hapax.rate.plan"
    _description = "Hapax Rate Plan"
    _inherit = ["mail.thread", "hapax.audit.mixin"]
    _order = "sequence asc, id asc"
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    public = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    project_id = fields.Many2one(
        "hapax.project",
        required=True,
        check_company=True,
        ondelete="cascade",
    )
    vehicle_id = fields.Many2one(
        "hapax.vehicle",
        check_company=True,
        ondelete="cascade",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    name = fields.Char(required=True)
    pricing_model = fields.Selection(
        [("daily_flat", "Daily flat rate")],
        required=True,
        default="daily_flat",
    )
    daily_rate = fields.Monetary(required=True, currency_field="currency_id")
    weekly_rate = fields.Monetary(currency_field="currency_id")
    weekend_rate = fields.Monetary(currency_field="currency_id")
    cleaning_fee = fields.Monetary(currency_field="currency_id")
    deposit_amount = fields.Monetary(currency_field="currency_id")
    minimum_days = fields.Integer(default=1)
    valid_from = fields.Date()
    valid_to = fields.Date()

    @api.constrains("company_id", "project_id", "vehicle_id")
    def _check_scope(self):
        for record in self:
            if record.project_id and record.project_id.company_id != record.company_id:
                raise ValidationError("Rate plan company must match the project company.")
            if record.vehicle_id and record.vehicle_id.project_id != record.project_id:
                raise ValidationError("Vehicle-specific rate plans must use the same project as the vehicle.")

    @api.constrains("minimum_days", "daily_rate", "valid_from", "valid_to")
    def _check_values(self):
        for record in self:
            if record.minimum_days < 1:
                raise ValidationError("Minimum days must be at least one day.")
            if record.daily_rate <= 0:
                raise ValidationError("Daily rate must be greater than zero.")
            if record.valid_from and record.valid_to and record.valid_to < record.valid_from:
                raise ValidationError("Rate plan end date must be after the start date.")

    def to_public_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "pricingModel": self.pricing_model,
            "dailyRate": float(self.daily_rate or 0.0),
            "weeklyRate": float(self.weekly_rate or 0.0),
            "weekendRate": float(self.weekend_rate or 0.0),
            "cleaningFee": float(self.cleaning_fee or 0.0),
            "depositAmount": float(self.deposit_amount or 0.0),
            "minimumDays": self.minimum_days,
        }
