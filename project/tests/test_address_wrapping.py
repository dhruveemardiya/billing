import os
import unittest
import tempfile
from pypdf import PdfReader
import billing_engine
import pdf_generator
import template_detector

class AddressWrappingTests(unittest.TestCase):
    def setUp(self):
        self.sample_address = "Building no.7, 404, Anandnagar flats, behind shell petrol pump, Prahlad Nagar, Ahmedabad, Gujarat"

    def _build_consumer(self, address: str):
        return {
            "customer_id": "ADDR_TEST_001",
            "consumer_name": "Dhruvi",
            "address": address,
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
            "previous_payment_date": "20/05/2026",
        }

    def test_complete_address_preserved_in_classic_pdf(self):
        template_path = "demo.pdf"
        if not os.path.exists(template_path):
            self.skipTest("demo.pdf not found")

        consumer = self._build_consumer(self.sample_address)
        bill = billing_engine.compute_bill(consumer)
        ts = template_detector.detect_template_structure(template_path)

        with tempfile.TemporaryDirectory() as out_dir:
            out_pdf = os.path.join(out_dir, "test_address_classic.pdf")
            pdf_generator.generate_bill_pdf(
                template_path, consumer, bill, out_pdf, template_structure=ts
            )
            self.assertTrue(os.path.exists(out_pdf))

            reader = PdfReader(out_pdf)
            page_text = reader.pages[0].extract_text()

            # Verify all parts of the address are present in the PDF text
            norm_text = " ".join(page_text.upper().split())
            self.assertIn("BUILDING NO.7", norm_text)
            self.assertIn("404", norm_text)
            self.assertIn("ANANDNAGAR FLATS", norm_text)
            self.assertIn("BEHIND SHELL PETROL PUMP", norm_text)
            self.assertIn("PRAHLAD NAGAR", norm_text)
            self.assertIn("AHMEDABAD", norm_text)
            self.assertIn("GUJARAT", norm_text)
            self.assertIn("REGISTERED MOBILE NO :", norm_text)
            self.assertIn("REGISTERED E-MAIL ID :", norm_text)

    def test_complete_address_preserved_in_modern_pdf(self):
        template_path = "DEMONEWPDF.pdf"
        if not os.path.exists(template_path):
            self.skipTest("DEMONEWPDF.pdf not found")

        consumer = self._build_consumer(self.sample_address)
        bill = billing_engine.compute_bill(consumer)
        ts = template_detector.detect_template_structure(template_path)

        with tempfile.TemporaryDirectory() as out_dir:
            out_pdf = os.path.join(out_dir, "test_address_modern.pdf")
            pdf_generator.generate_bill_pdf(
                template_path, consumer, bill, out_pdf, template_structure=ts
            )
            self.assertTrue(os.path.exists(out_pdf))

            reader = PdfReader(out_pdf)
            page_text = reader.pages[0].extract_text()

            norm_text = " ".join(page_text.upper().split())
            self.assertIn("BUILDING NO.7", norm_text)
            self.assertIn("404", norm_text)
            self.assertIn("ANANDNAGAR FLATS", norm_text)
            self.assertIn("BEHIND SHELL PETROL PUMP", norm_text)
            self.assertIn("PRAHLAD NAGAR", norm_text)
            self.assertIn("AHMEDABAD", norm_text)
            self.assertIn("GUJARAT", norm_text)

if __name__ == "__main__":
    unittest.main()
