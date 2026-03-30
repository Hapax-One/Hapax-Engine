from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HapaxAvailabilityBlock(models.Model):
    _name = "hapax.availability.block"
    _description = "Hapax Availability Block"
    _inherit = ["hapax.audit.mixin"]
    _order = "date_start asc, id asc"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        ondelete="cascade",
    )
    project_id = fields.Many2one(
        "hapax.project",
        required=True,
        index=True,
        check_company=True,
        ondelete="cascade",
    )
    vehicle_id = fields.Many2one(
        "hapax.vehicle",
        required=True,
        index=True,
        check_company=True,
        ondelete="cascade",
    )
    booking_id = fields.Many2one(
        "hapax.booking",
        check_company=True,
        ondelete="set null",
    )
    block_type = fields.Selection(
        [
            ("booking", "Booking"),
            ("maintenance", "Maintenance"),
            ("manual", "Manual"),
            ("hold", "Hold"),
        ],
        default="booking",
        required=True,
    )
    state = fields.Selection(
        [
            ("active", "Active"),
            ("released", "Released"),
            ("cancelled", "Cancelled"),
        ],
        default="active",
        required=True,
        index=True,
    )
    date_start = fields.Datetime(required=True, index=True)
    date_end = fields.Datetime(required=True, index=True)
    notes = fields.Text()

    @api.constrains("date_start", "date_end", "company_id", "project_id", "vehicle_id")
    def _check_values(self):
        for record in self:
            if record.date_end <= record.date_start:
                raise ValidationError("Availability block end date must be after the start date.")
            if record.project_id.company_id != record.company_id:
                raise ValidationError("Availability block company must match the project company.")
            if record.vehicle_id.project_id != record.project_id:
                raise ValidationError("Availability blocks must use a vehicle from the same project.")
