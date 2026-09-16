import os
import unittest
import template_detector

class TemplateDetectorTests(unittest.TestCase):
    def test_detect_new_demo_structure(self):
        pdf_path = "DEMONEWPDF.pdf"
        if not os.path.exists(pdf_path):
            self.skipTest("DEMONEWPDF.pdf not found")

        ts = template_detector.detect_template_structure(pdf_path)
        self.assertEqual(ts.layout_type, "modern_manrope")
        self.assertEqual(ts.page_count, 2)
        self.assertTrue(len(ts.fields) > 30)

        keys = ts.fields_by_key.keys()
        self.assertIn("customer_id", keys)
        self.assertIn("consumer_name", keys)
        self.assertIn("headline_due_amount", keys)
        self.assertIn("meter_no", keys)
        self.assertIn("coupon_customer_id", keys)

        # Check customer_id uses Manrope-Bold for digit coverage
        cust_field = ts.fields_by_key["customer_id"]
        self.assertEqual(cust_field.font, "Manrope-Bold")

    def test_detect_classic_demo_structure(self):
        pdf_path = "demo.pdf"
        if not os.path.exists(pdf_path):
            self.skipTest("demo.pdf not found")

        ts = template_detector.detect_template_structure(pdf_path)
        self.assertEqual(ts.layout_type, "classic_neurial")
        self.assertEqual(ts.page_count, 2)
        self.assertTrue(len(ts.fields) > 30)
        self.assertIn("customer_id", ts.fields_by_key)

if __name__ == "__main__":
    unittest.main()
