import os
import unittest
import template_detector
import direct_bill_service

class TestTemplateSelection(unittest.TestCase):
    def test_parse_billing_month_year(self):
        cases = [
            ("July 2026", (7, 2026)),
            ("Jul 2026", (7, 2026)),
            ("August 2026", (8, 2026)),
            ("Aug 2026", (8, 2026)),
            ("2026-07", (7, 2026)),
            ("2026-08", (8, 2026)),
            ("07/2026", (7, 2026)),
            ("08/2026", (8, 2026)),
            ("June 2026", (6, 2026)),
            ("September 2026", (9, 2026)),
            ("February 2025", (2, 2025)),
            ("January 2027", (1, 2027)),
            ({"billing_month": "July 2026"}, (7, 2026)),
            ({"billing_month": "August 2026"}, (8, 2026)),
            (("July", 2026), (7, 2026)),
            (("August", 2026), (8, 2026)),
            ((7, 2026), (7, 2026)),
            ((8, 2026), (8, 2026)),
        ]
        for val, expected in cases:
            with self.subTest(val=val):
                res = template_detector.parse_billing_month_year(val)
                self.assertEqual(res, expected, f"Failed parsing {val}: expected {expected}, got {res}")

    def test_template_selection_rule(self):
        # Before July 2026 -> demo.pdf
        self.assertTrue(template_detector.get_template_for_billing_month("June 2026").endswith("demo.pdf"))
        self.assertTrue(template_detector.get_template_for_billing_month("February 2025").endswith("demo.pdf"))
        self.assertTrue(template_detector.get_template_for_billing_month("August 2025").endswith("demo.pdf"))
        self.assertTrue(template_detector.get_template_for_billing_month("January 2026").endswith("demo.pdf"))

        # July 2026 -> demo.pdf
        self.assertTrue(template_detector.get_template_for_billing_month("July 2026").endswith("demo.pdf"))
        self.assertTrue(template_detector.get_template_for_billing_month("Jul 2026").endswith("demo.pdf"))
        self.assertTrue(template_detector.get_template_for_billing_month("2026-07").endswith("demo.pdf"))
        self.assertTrue(template_detector.get_template_for_billing_month(("July", 2026)).endswith("demo.pdf"))

        # August 2026 -> DEMONEWPDF.pdf
        self.assertTrue(template_detector.get_template_for_billing_month("August 2026").endswith("DEMONEWPDF.pdf"))
        self.assertTrue(template_detector.get_template_for_billing_month("Aug 2026").endswith("DEMONEWPDF.pdf"))
        self.assertTrue(template_detector.get_template_for_billing_month("2026-08").endswith("DEMONEWPDF.pdf"))
        self.assertTrue(template_detector.get_template_for_billing_month(("August", 2026)).endswith("DEMONEWPDF.pdf"))

        # August 2026 and all future months -> DEMONEWPDF.pdf
        self.assertTrue(template_detector.get_template_for_billing_month("September 2026").endswith("DEMONEWPDF.pdf"))
        self.assertTrue(template_detector.get_template_for_billing_month("October 2026").endswith("DEMONEWPDF.pdf"))
        self.assertTrue(template_detector.get_template_for_billing_month("January 2027").endswith("DEMONEWPDF.pdf"))
        self.assertTrue(template_detector.get_template_for_billing_month("December 2028").endswith("DEMONEWPDF.pdf"))

    def test_single_month_direct_bill_july_2026(self):
        payload = {
            "customer_id": "TESTJULY2026",
            "consumer_name": "July Test User",
            "address": "123 Test Street, City",
            "mobile_no": "9876543210",
            "email": "test@example.com",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "July 2026",
            "end_month": "July 2026",
            "start_reading": 1000,
            "reference_units": 250,
        }
        res = direct_bill_service.process_direct_bill(payload)
        self.assertTrue(res["success"])
        self.assertEqual(res["bills"][0]["template_used"], "demo.pdf")
        pdf_path = res["bills"][0]["output_path"]
        self.assertTrue(os.path.exists(pdf_path))
        ts = template_detector.detect_template_structure(pdf_path)
        self.assertEqual(ts.layout_type, "classic_neurial", f"July 2026 should use demo.pdf (classic_neurial), got {ts.layout_type}")

    def test_single_month_direct_bill_august_2026(self):
        payload = {
            "customer_id": "TESTAUG2026",
            "consumer_name": "August Test User",
            "address": "123 Test Street, City",
            "mobile_no": "9876543210",
            "email": "test@example.com",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "August 2026",
            "end_month": "August 2026",
            "start_reading": 1000,
            "reference_units": 250,
        }
        res = direct_bill_service.process_direct_bill(payload)
        self.assertTrue(res["success"])
        self.assertEqual(res["bills"][0]["template_used"], "DEMONEWPDF.pdf")
        pdf_path = res["bills"][0]["output_path"]
        self.assertTrue(os.path.exists(pdf_path))
        ts = template_detector.detect_template_structure(pdf_path)
        self.assertEqual(ts.layout_type, "modern_manrope", f"August 2026 should use DEMONEWPDF.pdf (modern_manrope), got {ts.layout_type}")

    def test_multi_month_direct_bill_transition(self):
        # Multi-month batch spanning July 2026 and August 2026
        payload = {
            "customer_id": "TESTTRANS2026",
            "consumer_name": "Transition Test User",
            "address": "123 Test Street, City",
            "mobile_no": "9876543210",
            "email": "test@example.com",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "June 2026",
            "end_month": "August 2026",
            "start_reading": 1000,
            "reference_units": 250,
        }
        res = direct_bill_service.process_direct_bill(payload)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["bills"]), 3)

        # Bill 0: June 2026 -> demo.pdf (classic_neurial)
        self.assertEqual(res["bills"][0]["template_used"], "demo.pdf")
        ts0 = template_detector.detect_template_structure(res["bills"][0]["output_path"])
        self.assertEqual(ts0.layout_type, "classic_neurial", "June 2026 should use demo.pdf")

        # Bill 1: July 2026 -> demo.pdf (classic_neurial)
        self.assertEqual(res["bills"][1]["template_used"], "demo.pdf")
        ts1 = template_detector.detect_template_structure(res["bills"][1]["output_path"])
        self.assertEqual(ts1.layout_type, "classic_neurial", "July 2026 should use demo.pdf")

        # Bill 2: August 2026 -> DEMONEWPDF.pdf (modern_manrope)
        self.assertEqual(res["bills"][2]["template_used"], "DEMONEWPDF.pdf")
        ts2 = template_detector.detect_template_structure(res["bills"][2]["output_path"])
        self.assertEqual(ts2.layout_type, "modern_manrope", "August 2026 should use DEMONEWPDF.pdf")

    def test_bimonthly_direct_bill_transition(self):
        # Bi-monthly June 2026 to August 2026
        payload = {
            "customer_id": "TESTBIMONTH26",
            "consumer_name": "BiMonthly Test User",
            "address": "123 Test Street, City",
            "mobile_no": "9876543210",
            "email": "test@example.com",
            "category": "Residential",
            "billing_cycle": "Bi-Monthly",
            "start_month": "June 2026",
            "end_month": "August 2026",
            "start_reading": 1000,
            "reference_units": 250,
        }
        res = direct_bill_service.process_direct_bill(payload)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["bills"]), 2)

        # Bill 0: June 2026 -> demo.pdf (classic_neurial)
        self.assertEqual(res["bills"][0]["template_used"], "demo.pdf")
        ts0 = template_detector.detect_template_structure(res["bills"][0]["output_path"])
        self.assertEqual(ts0.layout_type, "classic_neurial", "June 2026 should use demo.pdf")

        # Bill 1: August 2026 -> DEMONEWPDF.pdf (modern_manrope)
        self.assertEqual(res["bills"][1]["template_used"], "DEMONEWPDF.pdf")
        ts1 = template_detector.detect_template_structure(res["bills"][1]["output_path"])
        self.assertEqual(ts1.layout_type, "modern_manrope", "August 2026 should use DEMONEWPDF.pdf")

if __name__ == "__main__":
    unittest.main()
