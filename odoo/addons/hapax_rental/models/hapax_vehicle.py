import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HapaxVehicle(models.Model):
    _name = "hapax.vehicle"
    _description = "Hapax Vehicle"
    _inherit = ["mail.thread", "hapax.audit.mixin"]
    _order = "sequence asc, name asc, id asc"
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    published = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        tracking=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    project_id = fields.Many2one(
        "hapax.project",
        required=True,
        tracking=True,
        check_company=True,
        ondelete="cascade",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    name = fields.Char(required=True, tracking=True)
    slug = fields.Char(required=True, tracking=True)
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("available", "Available"),
            ("maintenance", "Maintenance"),
            ("inactive", "Inactive"),
        ],
        required=True,
        default="draft",
        tracking=True,
    )
    make = fields.Char()
    model = fields.Char()
    year = fields.Integer()
    category = fields.Char()
    summary = fields.Char()
    description = fields.Html()
    transmission = fields.Selection(
        [
            ("automatic", "Automatic"),
            ("manual", "Manual"),
        ],
        default="automatic",
    )
    fuel_type = fields.Selection(
        [
            ("gasoline", "Gasoline"),
            ("diesel", "Diesel"),
            ("hybrid", "Hybrid"),
            ("electric", "Electric"),
        ],
        default="gasoline",
    )
    seats = fields.Integer(default=4)
    luggage_count = fields.Integer(default=2)
    location_name = fields.Char()
    plate_number = fields.Char()
    vin = fields.Char()
    image_url = fields.Char()
    hero_image_url = fields.Char()
    gallery_json = fields.Text(default="[]")
    features_json = fields.Text(default="[]")
    daily_rate = fields.Monetary(currency_field="currency_id", tracking=True)
    deposit_amount = fields.Monetary(currency_field="currency_id")
    minimum_days = fields.Integer(default=1)
    rating = fields.Float(default=4.8)
    review_count = fields.Integer(default=0)
    metadata_json = fields.Text(default="{}")

    _sql_constraints = [
        (
            "hapax_vehicle_project_slug_unique",
            "unique(project_id, slug)",
            "Vehicle slugs must be unique per project.",
        ),
        (
            "hapax_vehicle_company_plate_unique",
            "unique(company_id, plate_number)",
            "License plates must be unique per company.",
        ),
    ]

    @api.constrains("company_id", "project_id")
    def _check_project_company(self):
        for record in self:
            if record.project_id and record.project_id.company_id != record.company_id:
                raise ValidationError("Vehicle company must match the project company.")

    @api.constrains("slug", "minimum_days")
    def _check_vehicle_values(self):
        for record in self:
            if not record.slug or "." in record.slug or " " in record.slug:
                raise ValidationError("Vehicle slug must be a bare slug without spaces or dots.")
            if record.minimum_days < 1:
                raise ValidationError("Minimum rental duration must be at least one day.")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            project_id = values.get("project_id")
            if project_id and not values.get("company_id"):
                project = self.env["hapax.project"].browse(project_id)
                values["company_id"] = project.company_id.id
        return super().create(vals_list)

    def _safe_json_list(self, value):
        if not value:
            return []
        try:
            data = json.loads(value)
        except (TypeError, ValueError):
            return []
        return data if isinstance(data, list) else []

    def _money_payload(self, amount):
        currency = self.currency_id.name or "USD"
        return {
            "amount": float(amount or 0.0),
            "currency": currency,
            "formatted": f"{currency} {float(amount or 0.0):,.2f}",
        }

    def to_storefront_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "status": self.status,
            "category": self.category,
            "summary": self.summary,
            "description": self.description,
            "make": self.make,
            "model": self.model,
            "year": self.year,
            "transmission": self.transmission,
            "fuelType": self.fuel_type,
            "seats": self.seats,
            "luggageCount": self.luggage_count,
            "locationName": self.location_name,
            "plateNumber": self.plate_number,
            "imageUrl": self.image_url or self.hero_image_url,
            "heroImageUrl": self.hero_image_url or self.image_url,
            "gallery": self._safe_json_list(self.gallery_json),
            "features": self._safe_json_list(self.features_json),
            "dailyRate": self._money_payload(self.daily_rate),
            "depositAmount": self._money_payload(self.deposit_amount),
            "minimumDays": self.minimum_days,
            "rating": self.rating,
            "reviewCount": self.review_count,
        }
