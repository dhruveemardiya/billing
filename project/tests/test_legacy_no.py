import os
import unittest
import pypdf
import tempfile
import json
import shutil

import legacy_store
import direct_bill_service
import excel_reader
import pdf_mapper
import pdf_generator
import billing_engine
import template_detector


class TestLegacyNoGeneration(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_store_file = legacy_store.LEGACY_STORE_FILE
        self.test_store_file = os.path.join(self.test_dir, "test_legacy_store.json")
        legacy_store.LEGACY_STORE_FILE = self.test_store_file

    def tearDown(self):
        legacy_store.LEGACY_STORE_FILE = self.orig_store_file
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_same_customer_gets_same_legacy_no(self):
        cust_id = "CUST_TEST_001"
        legacy1 = legacy_store.get_or_create_legacy_no(cust_id)
        legacy2 = legacy_store.get_or_create_legacy_no(cust_id)
        self.assertEqual(legacy1, legacy2, "Same customer must get the exact same Legacy No.")
        self.assertTrue(legacy1.isdigit(), "Legacy No must be numeric.")
        self.assertEqual(len(legacy1), 6, "Legacy No must be 6 digits.")

    def test_different_customers_get_different_legacy_nos(self):
        cust_a = "CUST_A"
        cust_b = "CUST_B"
        cust_c = "CUST_C"
        leg_a = legacy_store.get_or_create_legacy_no(cust_a)
        leg_b = legacy_store.get_or_create_legacy_no(cust_b)
        leg_c = legacy_store.get_or_create_legacy_no(cust_c)

        self.assertNotEqual(leg_a, leg_b, "Different customers must get different Legacy Nos.")
        self.assertNotEqual(leg_a, leg_c, "Different customers must get different Legacy Nos.")
        self.assertNotEqual(leg_b, leg_c, "Different customers must get different Legacy Nos.")

    def test_persists_to_disk(self):
        cust_id = "PERSIST_TEST_99"
        legacy = legacy_store.get_or_create_legacy_no(cust_id)
        self.assertTrue(os.path.exists(self.test_store_file))

        with open(self.test_store_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn(cust_id, data)
        self.assertEqual(data[cust_id], legacy)

        # Simulating fresh reload
        loaded_again = legacy_store.get_or_create_legacy_no(cust_id)
        self.assertEqual(loaded_again, legacy)

    def test_direct_bill_multi_month_uses_same_legacy_no(self):
        form_data = {
            "customer_id": "DIRECT_USER_MULTI",
            "consumer_name": "Test Multi Month",
            "address": "123 Solar Street, Diu",
            "mobile_no": "9876543210",
            "email": "test@example.com",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "January 2026",
            "end_month": "March 2026",
            "start_reading": 1000,
            "reference_units": 150,
        }
        res = direct_bill_service.process_direct_bill(form_data)
        self.assertTrue(res["success"])
        self.assertEqual(res["total_bills"], 3)

        expected_legacy = legacy_store.get_or_create_legacy_no("DIRECT_USER_MULTI")
        for b in res["bills"]:
            consumer = b["consumer"]
            self.assertEqual(consumer["legacy_no"], expected_legacy,
                             "Every month in batch must share the exact same Legacy No.")
            self.assertEqual(b["summary"]["legacy_no"], expected_legacy)

    def test_pdf_contains_stored_legacy_no(self):
        cust_id = "PDF_VERIFY_CUST"
        expected_legacy = legacy_store.get_or_create_legacy_no(cust_id)

        consumer = {
            "customer_id": cust_id,
            "consumer_name": "RAMAJI BHAGVAN",
            "address": "Diu",
            "area": "DIU",
            "t_no": "3004645778",
            "billing_mode": "30 days",
            "bill_no": "214004095971",
            "category": "Residential",
            "billing_month": "June 2026",
            "reading_date": "02/06/2026",
            "bill_date": "10/06/2026",
            "due_date": "25/06/2026",
            "units": 89,
            "meter_no": "DND52642",
            "start_reading": 1000,
            "end_reading": 1089,
            "previous_payment": 200.0,
            "previous_payment_date": "20/05/2026"
        }
        bill = billing_engine.compute_bill(consumer)
        ts = template_detector.detect_template_structure("demo.pdf")
        out_pdf = os.path.join(self.test_dir, "demo_bill.pdf")
        pdf_generator.generate_bill_pdf("demo.pdf", consumer, bill, out_pdf, template_structure=ts)

        reader = pypdf.PdfReader(out_pdf)
        extracted_text = reader.pages[0].extract_text()
        self.assertIn("Legacy No", extracted_text)
        self.assertIn(expected_legacy, extracted_text,
                      f"Stored Legacy No '{expected_legacy}' must appear in the generated PDF text.")


if __name__ == "__main__":
    unittest.main()
