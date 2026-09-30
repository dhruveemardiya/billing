import os
import unittest
import pypdf
import font_manager
import direct_bill_service


class GujaratiFontTests(unittest.TestCase):
    def test_gujarati_font_files_exist_in_project(self):
        reg_path, bold_path = font_manager.get_gujarati_font_paths()
        self.assertIsNotNone(reg_path)
        self.assertTrue(os.path.exists(reg_path), f"Regular font not found at {reg_path}")
        self.assertIsNotNone(bold_path)
        self.assertTrue(os.path.exists(bold_path), f"Bold font not found at {bold_path}")

    def test_gujarati_font_startup_validation(self):
        diag = font_manager.validate_gujarati_font()
        self.assertEqual(diag["status"], "ok")
        self.assertEqual(diag["regular_font"], "NotoSansGujarati")
        self.assertEqual(diag["bold_font"], "NotoSansGujarati-Bold")
        self.assertGreater(diag["sample_extracted_count"], 0)

    def test_pgvcl_pdf_renders_actual_gujarati_characters(self):
        payload = {
            "bill_type": "PGVCL Bill",
            "customer_id": "GUJ_TEST_999",
            "consumer_name": "GUJARATI TEST USER",
            "address": "Opp. Swaminarayan Temple, Gondal",
            "mobile_no": "9876543210",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "August 2026",
            "end_month": "August 2026",
            "start_reading": 2000,
            "reference_units": 200,
        }
        res = direct_bill_service.process_direct_bill(payload)
        self.assertTrue(res["success"])
        pdf_path = res["bills"][0]["output_path"]
        self.assertTrue(os.path.exists(pdf_path))

        reader = pypdf.PdfReader(pdf_path)
        page = reader.pages[0]
        text = page.extract_text()

        # Gujarati Unicode range: 0x0A80 to 0x0AFF
        guj_chars = [ch for ch in text if 0x0A80 <= ord(ch) <= 0x0AFF]
        self.assertGreater(len(guj_chars), 300, "Expected over 300 Gujarati characters in the generated bill")
        self.assertIn("નોટીસ", text)
        self.assertIn("વીજ અધિનિયમ", text)
        self.assertIn("ભૂલચૂક લેવી દેવી", text)

        # Confirm NotoSansGujarati is embedded in the PDF
        font_dict = page.get("/Resources", {}).get("/Font", {})
        font_names = [str(font_dict[k].get_object().get("/BaseFont", "")) for k in font_dict]
        self.assertTrue(
            any("NotoSansGujarati" in fn for fn in font_names),
            f"NotoSansGujarati was not embedded in the PDF fonts: {font_names}"
        )


if __name__ == "__main__":
    unittest.main()
