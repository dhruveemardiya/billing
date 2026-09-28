import os
import unittest
import template_detector
import direct_bill_service
from app import app


class TestPGVCLBill(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess["authenticated"] = True
            sess["user"] = "Admin"

    def test_pgvcl_template_exists_and_detects(self):
        """Verify PGVCL template structure detection returns layout_type == 'pgvcl'."""
        self.assertTrue(os.path.exists(template_detector.PGVCL_TEMPLATE_PATH))
        ts = template_detector.detect_template_structure(template_detector.PGVCL_TEMPLATE_PATH)
        self.assertEqual(ts.layout_type, "pgvcl")
        self.assertEqual(ts.page_count, 1)
        self.assertIn("consumer_name", ts.fields_by_key)
        self.assertIn("customer_id", ts.fields_by_key)
        self.assertIn("net_bill_amount", ts.fields_by_key)
        self.assertIn("bill_date", ts.fields_by_key)
        self.assertIn("due_date", ts.fields_by_key)
        self.assertIn("consumption_units", ts.fields_by_key)

    def test_direct_bill_pgvcl_generation(self):
        """Verify process_direct_bill generates a PGVCL bill when bill_type is 'PGVCL Bill'."""
        payload = {
            "bill_type": "PGVCL Bill",
            "customer_id": "PGVCL123456",
            "consumer_name": "PGVCL Consumer",
            "address": "Opp. Power Substation, Rajkot",
            "mobile_no": "9876543210",
            "email": "consumer@pgvcl.com",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "July 2026",
            "end_month": "July 2026",
            "start_reading": 500,
            "reference_units": 200,
        }
        res = direct_bill_service.process_direct_bill(payload)
        self.assertTrue(res["success"])
        self.assertEqual(res["bill_type"], "PGVCL Bill")
        self.assertEqual(len(res["bills"]), 1)
        bill = res["bills"][0]
        self.assertEqual(bill["template_used"], "PGVCL.jpeg")
        self.assertTrue(os.path.exists(bill["output_path"]))
        self.assertGreater(os.path.getsize(bill["output_path"]), 10000)

    def test_direct_bill_torrent_generation(self):
        """Verify process_direct_bill generates a Torrent bill when bill_type is 'Torrent Bill'."""
        payload = {
            "bill_type": "Torrent Bill",
            "customer_id": "TORRENT123",
            "consumer_name": "Torrent Consumer",
            "address": "123 Torrent Marg, Ahmedabad",
            "mobile_no": "9876543210",
            "email": "consumer@torrent.com",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "July 2026",
            "end_month": "July 2026",
            "start_reading": 500,
            "reference_units": 200,
        }
        res = direct_bill_service.process_direct_bill(payload)
        self.assertTrue(res["success"])
        self.assertEqual(res["bill_type"], "Torrent Bill")
        self.assertEqual(len(res["bills"]), 1)
        bill = res["bills"][0]
        self.assertEqual(bill["template_used"], "demo.pdf")
        self.assertTrue(os.path.exists(bill["output_path"]))

    def test_dynamic_bill_type_switching(self):
        """Verify dynamic template selection switches cleanly between Torrent and PGVCL for the same user."""
        base_payload = {
            "customer_id": "SWITCHTEST01",
            "consumer_name": "Switching Consumer",
            "address": "456 Grid Lane",
            "mobile_no": "9876543210",
            "email": "switch@test.com",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "August 2026",
            "end_month": "August 2026",
            "start_reading": 1000,
            "reference_units": 150,
        }

        # 1. Generate with Torrent Bill
        torrent_payload = {**base_payload, "bill_type": "Torrent Bill"}
        res_torrent = direct_bill_service.process_direct_bill(torrent_payload)
        self.assertTrue(res_torrent["success"])
        self.assertEqual(res_torrent["bill_type"], "Torrent Bill")
        # August 2026 Torrent uses DEMONEWPDF.pdf
        self.assertEqual(res_torrent["bills"][0]["template_used"], "DEMONEWPDF.pdf")

        # 2. Generate with PGVCL Bill
        pgvcl_payload = {**base_payload, "bill_type": "PGVCL Bill"}
        res_pgvcl = direct_bill_service.process_direct_bill(pgvcl_payload)
        self.assertTrue(res_pgvcl["success"])
        self.assertEqual(res_pgvcl["bill_type"], "PGVCL Bill")
        self.assertEqual(res_pgvcl["bills"][0]["template_used"], "PGVCL.jpeg")

    def test_api_route_generate_bill_direct_pgvcl(self):
        """Test /api/generate-bill-direct endpoint accepts bill_type='PGVCL Bill'."""
        data = {
            "bill_type": "PGVCL Bill",
            "customer_id": "APIPGVCL1",
            "consumer_name": "API PGVCL User",
            "address": "Ring Road, Rajkot",
            "mobile_no": "9876543210",
            "email": "apipgvcl@test.com",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "July 2026",
            "end_month": "July 2026",
            "start_reading": "100",
            "reference_units": "180",
        }
        resp = self.client.post("/api/generate-bill-direct", json=data)
        self.assertEqual(resp.status_code, 200)
        json_data = resp.get_json()
        self.assertTrue(json_data.get("success"))
        self.assertEqual(json_data.get("bill_type"), "PGVCL Bill")
        self.assertEqual(json_data["bills"][0]["template_used"], "PGVCL.jpeg")


    def test_persistent_customer_identifiers_and_sequential_bill_no(self):
        """Verify same customer retains persistent identifiers across multi-month generation with sequential bill numbers."""
        payload = {
            "bill_type": "PGVCL Bill",
            "customer_id": "PERSIST_TEST_01",
            "consumer_name": "Persistent Consumer",
            "address": "Opp. Railway Station",
            "village_name": "VERAVAL",
            "village": "Veraval",
            "taluka": "Veraval",
            "district": "GIR SOMNATH",
            "mobile_no": "9876543210",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "January 2026",
            "end_month": "March 2026",
            "start_reading": 1000,
            "reference_units": 200,
        }
        res = direct_bill_service.process_direct_bill(payload)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["bills"]), 3)

        b0_cons = res["bills"][0]["consumer"]
        b1_cons = res["bills"][1]["consumer"]
        b2_cons = res["bills"][2]["consumer"]

        # Same customer = same Meter No, Census Code, Feeder Code, Route Code
        self.assertEqual(b0_cons["meter_no"], b1_cons["meter_no"])
        self.assertEqual(b1_cons["meter_no"], b2_cons["meter_no"])
        self.assertTrue(b0_cons["meter_no"].startswith("ONE-"))

        self.assertEqual(b0_cons["census_code"], b1_cons["census_code"])
        self.assertEqual(b1_cons["census_code"], b2_cons["census_code"])

        self.assertEqual(b0_cons["feeder_code"], b1_cons["feeder_code"])
        self.assertEqual(b0_cons["route_code"], b1_cons["route_code"])
        self.assertEqual(b0_cons["meter_status"], b1_cons["meter_status"])
        self.assertEqual(b0_cons["mf"], b1_cons["mf"])
        self.assertEqual(b0_cons["mtr_chg_code"], b1_cons["mtr_chg_code"])

        # Bill No increments sequentially (+0, +1, +2)
        b0_num = int(b0_cons["bill_no"])
        b1_num = int(b1_cons["bill_no"])
        b2_num = int(b2_cons["bill_no"])
        self.assertEqual(b1_num, b0_num + 1)
        self.assertEqual(b2_num, b0_num + 2)

        # Different customer gets different identifiers
        payload_b = {**payload, "customer_id": "PERSIST_TEST_02"}
        res_b = direct_bill_service.process_direct_bill(payload_b)
        b_cons = res_b["bills"][0]["consumer"]
        self.assertNotEqual(b_cons["meter_no"], b0_cons["meter_no"])

    def test_pgvcl_bimonthly_billing_and_history(self):
        """Verify Bi-Monthly billing generates 2-month periods and dynamic 3-period history."""
        payload = {
            "bill_type": "PGVCL Bill",
            "customer_id": "BIMONTH_TEST_01",
            "consumer_name": "BiMonthly Consumer",
            "address": "Bhavnagar Highway",
            "mobile_no": "9876543210",
            "category": "Residential",
            "billing_cycle": "Bi-Monthly",
            "start_month": "February 2026",
            "end_month": "April 2026",
            "start_reading": 2000,
            "reference_units": 350,
        }
        res = direct_bill_service.process_direct_bill(payload)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["bills"]), 2)

        b0_cons = res["bills"][0]["consumer"]
        b1_cons = res["bills"][1]["consumer"]
        self.assertEqual(b0_cons["billing_month"], "February 2026")
        self.assertEqual(b1_cons["billing_month"], "April 2026")

        # History has 3 previous periods
        hist = b1_cons.get("last_3_months", [])
        self.assertEqual(len(hist), 3)
        # Chronological order
        for p in hist:
            self.assertIn("month", p)
            self.assertIn("units", p)
            self.assertIn("amount", p)
            self.assertGreater(p["units"], 0)
            self.assertGreater(p["amount"], 0)


if __name__ == "__main__":
    unittest.main()

