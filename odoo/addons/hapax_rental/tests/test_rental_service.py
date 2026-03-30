from datetime import datetime, timedelta

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHapaxRentalService(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env["res.company"].create({"name": "Hapax Test Company"})
        self.project = self.env["hapax.project"].create(
            {
                "name": "Hapax Test Tenant",
                "code": "HAPAXTEST",
                "company_id": self.company.id,
                "slug": "hapax-test",
                "primary_host": "hapax-test.gohapax.test",
                "status": "active",
            }
        )
        self.vehicle = self.env["hapax.vehicle"].create(
            {
                "company_id": self.company.id,
                "project_id": self.project.id,
                "name": "Test Vehicle",
                "slug": "test-vehicle",
                "status": "available",
                "published": True,
                "daily_rate": 75.0,
                "deposit_amount": 200.0,
            }
        )
        self.env["hapax.rate.plan"].create(
            {
                "company_id": self.company.id,
                "project_id": self.project.id,
                "vehicle_id": self.vehicle.id,
                "name": "Default",
                "daily_rate": 80.0,
                "cleaning_fee": 20.0,
                "deposit_amount": 250.0,
                "minimum_days": 1,
            }
        )

    def test_quote_vehicle_returns_pricing_payload(self):
        start_dt = datetime(2026, 4, 1, 10, 0, 0)
        end_dt = start_dt + timedelta(days=3)

        quote = self.env["hapax.rental.service"].get_quote(
            self.project,
            self.vehicle.slug,
            start_dt.isoformat(),
            end_dt.isoformat(),
        )

        self.assertTrue(quote["available"])
        self.assertEqual(quote["days"], 3)
        self.assertEqual(quote["dailyRate"]["amount"], 80.0)
        self.assertEqual(quote["cleaningFee"]["amount"], 20.0)
        self.assertEqual(quote["depositAmount"]["amount"], 250.0)
