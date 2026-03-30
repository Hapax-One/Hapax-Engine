{
    "name": "Hapax Rental",
    "version": "19.0.1.0.0",
    "summary": "Vehicle rental inventory, pricing, availability, and bookings for Hapax",
    "category": "Hidden",
    "license": "LGPL-3",
    "depends": ["hapax_identity"],
    "data": [
        "security/ir.model.access.csv",
        "security/hapax_rental_rules.xml",
        "data/ir_sequence.xml",
        "views/hapax_vehicle_views.xml",
        "views/hapax_booking_views.xml",
        "views/hapax_rate_plan_views.xml",
    ],
    "installable": True,
    "application": False,
}
