from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HapaxBooking(models.Model):
    _name = "hapax.booking"
    _description = "Hapax Booking"
    _inherit = ["mail.thread", "hapax.audit.mixin"]
    _order = "create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, default="New", copy=False, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
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
        ondelete="restrict",
    )
    rate_plan_id = fields.Many2one(
        "hapax.rate.plan",
        check_company=True,
        ondelete="set null",
    )
    membership_id = fields.Many2one(
        "hapax.membership",
        check_company=True,
        ondelete="set null",
    )
    customer_partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        ondelete="restrict",
    )
    customer_user_id = fields.Many2one(
        "res.users",
        check_company=True,
        ondelete="set null",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    date_start = fields.Datetime(required=True, index=True)
    date_end = fields.Datetime(required=True, index=True)
    pickup_location = fields.Char()
    return_location = fields.Char()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending"),
            ("confirmed", "Confirmed"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    quoted_days = fields.Integer(default=1)
    quoted_daily_rate = fields.Monetary(currency_field="currency_id")
    quoted_subtotal = fields.Monetary(currency_field="currency_id")
    cleaning_fee = fields.Monetary(currency_field="currency_id")
    deposit_amount = fields.Monetary(currency_field="currency_id")
    quoted_total = fields.Monetary(currency_field="currency_id")
    source_host = fields.Char()
    source_channel = fields.Char(default="storefront")
    notes = fields.Text()

    @api.constrains("company_id", "project_id", "vehicle_id", "membership_id", "date_start", "date_end")
    def _check_values(self):
        for record in self:
            if record.date_end <= record.date_start:
                raise ValidationError("Booking end date must be after the start date.")
            if record.project_id.company_id != record.company_id:
                raise ValidationError("Booking company must match the project company.")
            if record.vehicle_id.project_id != record.project_id:
                raise ValidationError("Booking vehicle must belong to the same project.")
            if record.membership_id and record.membership_id.project_id != record.project_id:
                raise ValidationError("Booking membership must belong to the same project.")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", "New") == "New":
                values["name"] = (
                    self.env["ir.sequence"].next_by_code("hapax.booking") or "New"
                )
        return super().create(vals_list)

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})
        self.env["hapax.availability.block"].sudo().search(
            [("booking_id", "in", self.ids), ("state", "=", "active")]
        ).write({"state": "cancelled"})

    def to_public_payload(self):
        self.ensure_one()
        currency = self.currency_id.name or "USD"
        return {
            "id": self.id,
            "reference": self.name,
            "state": self.state,
            "sourceChannel": self.source_channel or "storefront",
            "vehicle": {
                "id": self.vehicle_id.id,
                "slug": self.vehicle_id.slug,
                "name": self.vehicle_id.name,
                "imageUrl": self.vehicle_id.image_url or self.vehicle_id.hero_image_url,
                "plateNumber": self.vehicle_id.plate_number,
                "locationName": self.vehicle_id.location_name,
            },
            "dateStart": fields.Datetime.to_string(self.date_start),
            "dateEnd": fields.Datetime.to_string(self.date_end),
            "pickupLocation": self.pickup_location,
            "returnLocation": self.return_location,
            "quotedDays": self.quoted_days,
            "quotedTotal": {
                "amount": float(self.quoted_total or 0.0),
                "currency": currency,
                "formatted": f"{currency} {float(self.quoted_total or 0.0):,.2f}",
            },
            "depositAmount": {
                "amount": float(self.deposit_amount or 0.0),
                "currency": currency,
                "formatted": f"{currency} {float(self.deposit_amount or 0.0):,.2f}",
            },
            "customer": {
                "id": self.customer_partner_id.id,
                "name": self.customer_partner_id.name,
                "email": self.customer_partner_id.email,
            },
        }
