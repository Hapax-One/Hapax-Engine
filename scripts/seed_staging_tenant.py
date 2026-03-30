import json
import os
from datetime import timedelta

from odoo import fields


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


project_slug = os.environ.get("HAPAX_SEED_PROJECT_SLUG", "car-rental-staging").strip()
project_name = os.environ.get("HAPAX_SEED_PROJECT_NAME", "Hapax Car Rental Staging").strip()
project_code = os.environ.get("HAPAX_SEED_PROJECT_CODE", "HAPAX-STAGING-CAR").strip()
primary_host = os.environ.get("HAPAX_SEED_PRIMARY_HOST", "staging-app.gohapax.com").strip()
alias_hosts = os.environ.get("HAPAX_SEED_ALIAS_HOSTS", "staging-api.gohapax.com\nlocalhost")
website_url = os.environ.get("HAPAX_SEED_WEBSITE_URL", f"https://{primary_host}").strip()
brand_name = os.environ.get("HAPAX_SEED_BRAND_NAME", "Hapax Car Rental").strip()
brand_color = os.environ.get("HAPAX_SEED_BRAND_COLOR", "#0F766E").strip()
support_email = os.environ.get("HAPAX_SEED_SUPPORT_EMAIL", "hello@gohapax.com").strip()
support_phone = os.environ.get("HAPAX_SEED_SUPPORT_PHONE", "+1 876 555 0199").strip()

admin_email = required("HAPAX_STAGING_ADMIN_EMAIL")
admin_password = required("HAPAX_STAGING_ADMIN_PASSWORD")
customer_email = required("HAPAX_STAGING_CUSTOMER_EMAIL")
customer_password = required("HAPAX_STAGING_CUSTOMER_PASSWORD")

ICP = env["ir.config_parameter"].sudo()
ICP.set_param("hapax.base_domain", os.environ.get("HAPAX_BASE_DOMAIN", "gohapax.com"))
ICP.set_param(
    "hapax.api_cookie_domain",
    os.environ.get("HAPAX_API_COOKIE_DOMAIN", ".gohapax.com"),
)

usd = env.ref("base.USD", raise_if_not_found=False)
company_vals = {
    "name": project_name,
    "hapax_slug": project_slug,
    "hapax_primary_host": primary_host,
    "hapax_brand_name": brand_name,
    "hapax_public_email": support_email,
    "hapax_support_phone": support_phone,
}
company = env["res.company"].sudo().search([("hapax_slug", "=", project_slug)], limit=1)
if company:
    company.write(company_vals)
else:
    if usd:
        company_vals["currency_id"] = usd.id
    company = env["res.company"].sudo().create(company_vals)
    if usd:
        company.write({"currency_id": usd.id})

project_vals = {
    "name": project_name,
    "code": project_code,
    "company_id": company.id,
    "slug": project_slug,
    "primary_host": primary_host,
    "alias_hosts": alias_hosts,
    "website_url": website_url,
    "brand_name": brand_name,
    "brand_color": brand_color,
    "support_email": support_email,
    "support_phone": support_phone,
    "status": "active",
    "metadata_json": json.dumps({"seededBy": "codex", "environment": "staging"}),
    "active": True,
}
project = env["hapax.project"].sudo().search([("slug", "=", project_slug)], limit=1)
if project:
    project.write(project_vals)
else:
    project = env["hapax.project"].sudo().create(project_vals)

portal_group = env.ref("base.group_portal")


def ensure_user(email, password, name, role):
    partner = env["res.partner"].sudo().search([("email", "=", email)], limit=1)
    if partner:
        partner.write({"name": name, "phone": support_phone})
    else:
        partner = env["res.partner"].sudo().create(
            {"name": name, "email": email, "phone": support_phone}
        )

    user = env["res.users"].sudo().search([("login", "=", email)], limit=1)
    user_vals = {
        "name": name,
        "login": email,
        "email": email,
        "partner_id": partner.id,
        "company_id": company.id,
        "company_ids": [(6, 0, [company.id])],
        "password": password,
    }
    if user:
        user.with_context(no_reset_password=True).write(user_vals)
        if portal_group.id not in user.group_ids.ids:
            user.write({"group_ids": [(4, portal_group.id)]})
    else:
        user = env["res.users"].sudo().with_context(no_reset_password=True).create(
            {
                **user_vals,
                "group_ids": [(6, 0, [portal_group.id])],
            }
        )

    membership = env["hapax.membership"].sudo().search(
        [("project_id", "=", project.id), ("partner_id", "=", partner.id)],
        limit=1,
    )
    membership_vals = {
        "company_id": company.id,
        "project_id": project.id,
        "partner_id": partner.id,
        "user_id": user.id,
        "role": role,
        "status": "active",
        "is_primary": True,
    }
    if membership:
        membership.write(membership_vals)
    else:
        membership = env["hapax.membership"].sudo().create(membership_vals)
    return user, partner, membership


admin_user, admin_partner, admin_membership = ensure_user(
    admin_email,
    admin_password,
    "Hapax Staging Admin",
    "owner",
)
customer_user, customer_partner, customer_membership = ensure_user(
    customer_email,
    customer_password,
    "Hapax Staging Customer",
    "customer",
)

vehicles_payload = [
    {
        "name": "Toyota Corolla Cross",
        "slug": "toyota-corolla-cross",
        "status": "available",
        "published": True,
        "make": "Toyota",
        "model": "Corolla Cross",
        "year": 2024,
        "category": "SUV",
        "summary": "Compact SUV for airport pickups and island driving.",
        "description": "Reliable compact SUV with room for five passengers and luggage.",
        "location_name": "Montego Bay",
        "transmission": "automatic",
        "fuel_type": "gasoline",
        "seats": 5,
        "luggage_count": 3,
        "plate_number": "HAPAX-101",
        "daily_rate": 82.0,
        "deposit_amount": 250.0,
        "minimum_days": 2,
        "features_json": json.dumps(
            ["Bluetooth", "Backup camera", "Airport pickup"]
        ),
        "gallery_json": json.dumps([]),
        "image_url": "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=1200&q=80",
        "hero_image_url": "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?auto=format&fit=crop&w=1600&q=80",
    },
    {
        "name": "Suzuki Swift",
        "slug": "suzuki-swift",
        "status": "available",
        "published": True,
        "make": "Suzuki",
        "model": "Swift",
        "year": 2023,
        "category": "Compact",
        "summary": "Easy city runabout with excellent fuel economy.",
        "description": "Compact hatchback ideal for Kingston and coastal weekend trips.",
        "location_name": "Kingston",
        "transmission": "automatic",
        "fuel_type": "gasoline",
        "seats": 5,
        "luggage_count": 2,
        "plate_number": "HAPAX-102",
        "daily_rate": 58.0,
        "deposit_amount": 180.0,
        "minimum_days": 1,
        "features_json": json.dumps(["Apple CarPlay", "A/C", "USB charging"]),
        "gallery_json": json.dumps([]),
        "image_url": "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?auto=format&fit=crop&w=1200&q=80",
        "hero_image_url": "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?auto=format&fit=crop&w=1600&q=80",
    },
]
vehicles = []
for payload in vehicles_payload:
    payload = {**payload, "company_id": company.id, "project_id": project.id}
    vehicle = env["hapax.vehicle"].sudo().search(
        [("project_id", "=", project.id), ("slug", "=", payload["slug"])],
        limit=1,
    )
    if vehicle:
        vehicle.write(payload)
    else:
        vehicle = env["hapax.vehicle"].sudo().create(payload)
    vehicles.append(vehicle)

rate_plan_vals = {
    "company_id": company.id,
    "project_id": project.id,
    "name": "Public Standard Rate",
    "public": True,
    "daily_rate": 76.0,
    "cleaning_fee": 18.0,
    "deposit_amount": 220.0,
    "minimum_days": 1,
}
rate_plan = env["hapax.rate.plan"].sudo().search(
    [
        ("project_id", "=", project.id),
        ("name", "=", "Public Standard Rate"),
        ("vehicle_id", "=", False),
    ],
    limit=1,
)
if rate_plan:
    rate_plan.write(rate_plan_vals)
else:
    rate_plan = env["hapax.rate.plan"].sudo().create(rate_plan_vals)

start_dt = fields.Datetime.now() + timedelta(days=7)
end_dt = start_dt + timedelta(days=3)
existing_booking = env["hapax.booking"].sudo().search(
    [
        ("project_id", "=", project.id),
        ("customer_partner_id", "=", customer_partner.id),
        ("vehicle_id", "=", vehicles[0].id),
        ("state", "!=", "cancelled"),
    ],
    limit=1,
)
if not existing_booking:
    env["hapax.rental.service"].sudo().create_booking(
        project,
        {
            "vehicleId": vehicles[0].id,
            "dateStart": fields.Datetime.to_string(start_dt),
            "dateEnd": fields.Datetime.to_string(end_dt),
            "pickupLocation": vehicles[0].location_name,
            "returnLocation": vehicles[0].location_name,
            "sourceHost": primary_host,
            "sourceChannel": "seed",
            "notes": "Seeded staging booking",
        },
        {
            "user": customer_user,
            "partner": customer_partner,
            "membership": customer_membership,
        },
    )

env.cr.commit()
print(
    json.dumps(
        {
            "companyId": company.id,
            "projectId": project.id,
            "vehicleSlugs": [vehicle.slug for vehicle in vehicles],
            "adminEmail": admin_email,
            "customerEmail": customer_email,
        }
    )
)
