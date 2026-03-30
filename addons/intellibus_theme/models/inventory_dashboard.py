# -*- coding: utf-8 -*-

from uuid import uuid4

from odoo import _, api, models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def create_inventory_dashboard_item(self, payload):
        payload = payload or {}

        name = (payload.get("name") or "").strip()
        serial_number = (payload.get("serial_number") or "").strip()
        assigned_code = (payload.get("assigned_code") or serial_number or self._generate_inventory_code()).strip()
        description = (payload.get("description") or "").strip()
        tracking = (payload.get("tracking") or "none").strip() or "none"
        quantity = float(payload.get("quantity") or 0.0)
        category_id = int(payload.get("category_id") or 0)
        location_id = int(payload.get("location_id") or 0)
        track_as_asset = bool(payload.get("track_as_asset"))
        image_data = self._normalize_image_payload(payload.get("image_data"))

        if not name:
            raise UserError(_("Enter an item name."))
        if tracking not in {"none", "lot", "serial"}:
            raise UserError(_("Choose a valid tracking category."))
        if quantity < 0:
            raise UserError(_("Quantity cannot be negative."))
        if not category_id:
            raise UserError(_("Choose a category."))
        if quantity > 0 and not location_id:
            raise UserError(_("Choose a location for the opening quantity."))
        if tracking == "serial" and quantity > 1:
            raise UserError(_("Serial-tracked items can only be added one at a time."))
        if tracking == "serial" and not serial_number:
            raise UserError(_("Serial-tracked items require a serial number."))

        category = self.env["product.category"].browse(category_id).exists()
        if not category:
            raise UserError(_("The selected category is no longer available."))

        location = self.env["stock.location"].browse(location_id).exists() if location_id else self.env["stock.location"]
        if location and location.usage != "internal":
            raise UserError(_("Choose an internal stock location."))

        template_vals = {
            "name": name,
            "detailed_type": "product",
            "categ_id": category.id,
            "tracking": tracking,
            "description": description or False,
        }
        if image_data:
            template_vals["image_1920"] = image_data
        if "create_asset" in self._fields:
            template_vals["create_asset"] = track_as_asset

        template = self.create(template_vals)
        product = template.product_variant_id
        if not product:
            raise UserError(_("The item could not be created."))

        product.write({"barcode": assigned_code})

        lot = self.env["stock.lot"]
        if quantity > 0:
            if tracking in {"serial", "lot"}:
                lot_name = serial_number or assigned_code
                lot = self.env["stock.lot"].create(
                    {
                        "name": lot_name,
                        "product_id": product.id,
                        "company_id": self.env.company.id,
                    }
                )
            self.env["stock.quant"].sudo()._update_available_quantity(
                product,
                location,
                quantity,
                lot_id=lot or False,
            )

        return {
            "template_id": template.id,
            "product_id": product.id,
            "assigned_code": assigned_code,
            "lot_id": lot.id if lot else False,
        }

    @api.model
    def _generate_inventory_code(self):
        return "INV-%s" % uuid4().hex[:10].upper()

    @api.model
    def _normalize_image_payload(self, image_data):
        if not image_data:
            return False
        if "," in image_data:
            return image_data.split(",", 1)[1]
        return image_data
