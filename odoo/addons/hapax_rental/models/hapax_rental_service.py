from math import ceil

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HapaxRentalService(models.AbstractModel):
    _name = "hapax.rental.service"
    _description = "Hapax Rental Service"

    @api.model
    def _parse_window(self, start_value, end_value):
        start_dt = fields.Datetime.to_datetime(start_value)
        end_dt = fields.Datetime.to_datetime(end_value)
        if not start_dt or not end_dt:
            raise ValidationError("Both pickup and return datetimes are required.")
        if end_dt <= start_dt:
            raise ValidationError("Return datetime must be after pickup datetime.")
        return start_dt, end_dt

    @api.model
    def _calculate_day_count(self, start_dt, end_dt):
        seconds = (end_dt - start_dt).total_seconds()
        return max(1, ceil(seconds / 86400.0))

    @api.model
    def _find_vehicle(self, project, vehicle_ref):
        domain = [
            ("project_id", "=", project.id),
            ("active", "=", True),
        ]
        if isinstance(vehicle_ref, int):
            domain.append(("id", "=", vehicle_ref))
        elif str(vehicle_ref).isdigit():
            domain.append(("id", "=", int(vehicle_ref)))
        else:
            domain.append(("slug", "=", str(vehicle_ref)))
        vehicle = self.env["hapax.vehicle"].sudo().search(domain, limit=1)
        if not vehicle:
            raise ValidationError("Vehicle not found for this tenant.")
        return vehicle

    @api.model
    def _find_rate_plan(self, vehicle, start_dt, end_dt, public_only=False):
        day_count = self._calculate_day_count(start_dt, end_dt)
        candidates = self.env["hapax.rate.plan"].sudo().search(
            [
                ("company_id", "=", vehicle.company_id.id),
                ("project_id", "=", vehicle.project_id.id),
                ("active", "=", True),
                "|",
                ("vehicle_id", "=", False),
                ("vehicle_id", "=", vehicle.id),
            ],
            order="vehicle_id desc, sequence asc, id asc",
        )
        start_date = fields.Date.to_date(start_dt)
        end_date = fields.Date.to_date(end_dt)
        for plan in candidates:
            if public_only and not plan.public:
                continue
            if plan.minimum_days and day_count < plan.minimum_days:
                continue
            if plan.valid_from and start_date < plan.valid_from:
                continue
            if plan.valid_to and end_date > plan.valid_to:
                continue
            return plan
        return self.env["hapax.rate.plan"]

    @api.model
    def _get_conflicts(self, vehicle, start_dt, end_dt):
        return self.env["hapax.availability.block"].sudo().search(
            [
                ("vehicle_id", "=", vehicle.id),
                ("state", "=", "active"),
                ("date_start", "<", fields.Datetime.to_string(end_dt)),
                ("date_end", ">", fields.Datetime.to_string(start_dt)),
            ],
            order="date_start asc",
        )

    @api.model
    def _lock_vehicle(self, vehicle):
        self.env.cr.execute(
            f"SELECT id FROM {vehicle._table} WHERE id = %s FOR UPDATE",
            [vehicle.id],
        )

    @api.model
    def get_quote(self, project, vehicle_ref, start_value, end_value):
        project.ensure_one()
        vehicle = self._find_vehicle(project, vehicle_ref)
        start_dt, end_dt = self._parse_window(start_value, end_value)
        day_count = self._calculate_day_count(start_dt, end_dt)
        rate_plan = self._find_rate_plan(vehicle, start_dt, end_dt, public_only=True)
        conflicts = self._get_conflicts(vehicle, start_dt, end_dt)

        daily_rate = rate_plan.daily_rate if rate_plan else vehicle.daily_rate
        if not daily_rate:
            raise ValidationError("This vehicle does not have a public rate configured yet.")

        cleaning_fee = rate_plan.cleaning_fee if rate_plan else 0.0
        deposit_amount = (
            rate_plan.deposit_amount if rate_plan and rate_plan.deposit_amount else vehicle.deposit_amount
        )
        subtotal = daily_rate * day_count
        total = subtotal + cleaning_fee
        currency = vehicle.currency_id.name or "USD"

        return {
            "available": not bool(conflicts) and vehicle.status == "available" and vehicle.published,
            "vehicle": vehicle,
            "ratePlan": rate_plan,
            "startAt": fields.Datetime.to_string(start_dt),
            "endAt": fields.Datetime.to_string(end_dt),
            "days": day_count,
            "dailyRate": {
                "amount": float(daily_rate),
                "currency": currency,
                "formatted": f"{currency} {float(daily_rate):,.2f}",
            },
            "subtotal": {
                "amount": float(subtotal),
                "currency": currency,
                "formatted": f"{currency} {float(subtotal):,.2f}",
            },
            "cleaningFee": {
                "amount": float(cleaning_fee or 0.0),
                "currency": currency,
                "formatted": f"{currency} {float(cleaning_fee or 0.0):,.2f}",
            },
            "depositAmount": {
                "amount": float(deposit_amount or 0.0),
                "currency": currency,
                "formatted": f"{currency} {float(deposit_amount or 0.0):,.2f}",
            },
            "total": {
                "amount": float(total),
                "currency": currency,
                "formatted": f"{currency} {float(total):,.2f}",
            },
            "conflicts": [
                {
                    "id": block.id,
                    "type": block.block_type,
                    "startAt": fields.Datetime.to_string(block.date_start),
                    "endAt": fields.Datetime.to_string(block.date_end),
                }
                for block in conflicts
            ],
        }

    @api.model
    def create_booking(self, project, payload, principal):
        project.ensure_one()
        if not principal.get("partner"):
            raise ValidationError("A valid authenticated customer is required to book.")

        quote = self.get_quote(
            project,
            payload.get("vehicleId") or payload.get("vehicleSlug"),
            payload.get("dateStart"),
            payload.get("dateEnd"),
        )
        vehicle = quote["vehicle"]
        start_dt = fields.Datetime.to_datetime(quote["startAt"])
        end_dt = fields.Datetime.to_datetime(quote["endAt"])

        with self.env.cr.savepoint():
            self._lock_vehicle(vehicle)
            conflicts = self._get_conflicts(vehicle, start_dt, end_dt)
            if conflicts:
                raise ValidationError("The selected vehicle is no longer available for these dates.")

            booking = self.env["hapax.booking"].sudo().create(
                {
                    "company_id": project.company_id.id,
                    "project_id": project.id,
                    "vehicle_id": vehicle.id,
                    "rate_plan_id": quote["ratePlan"].id if quote["ratePlan"] else False,
                    "membership_id": principal.get("membership").id if principal.get("membership") else False,
                    "customer_partner_id": principal["partner"].id,
                    "customer_user_id": principal.get("user").id if principal.get("user") else False,
                    "date_start": quote["startAt"],
                    "date_end": quote["endAt"],
                    "pickup_location": payload.get("pickupLocation") or vehicle.location_name,
                    "return_location": payload.get("returnLocation") or vehicle.location_name,
                    "quoted_days": quote["days"],
                    "quoted_daily_rate": quote["dailyRate"]["amount"],
                    "quoted_subtotal": quote["subtotal"]["amount"],
                    "cleaning_fee": quote["cleaningFee"]["amount"],
                    "deposit_amount": quote["depositAmount"]["amount"],
                    "quoted_total": quote["total"]["amount"],
                    "notes": payload.get("notes"),
                    "source_host": payload.get("sourceHost"),
                    "source_channel": payload.get("sourceChannel") or "storefront",
                    "state": "confirmed",
                }
            )
            self.env["hapax.availability.block"].sudo().create(
                {
                    "company_id": project.company_id.id,
                    "project_id": project.id,
                    "vehicle_id": vehicle.id,
                    "booking_id": booking.id,
                    "block_type": "booking",
                    "state": "active",
                    "date_start": quote["startAt"],
                    "date_end": quote["endAt"],
                    "notes": booking.name,
                }
            )
        return booking
