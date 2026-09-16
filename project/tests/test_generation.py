import os
import unittest
import excel_reader
import billing_engine
import pdf_generator
import template_detector
from utils.file_utils import safe_customer_id, build_bill_filename

class GenerationTests(unittest.TestCase):
    def test_safe_customer_id_preserves_name_word_boundaries(self):
        self.assertEqual(safe_customer_id("AA Cariding", 1), "AA_Cariding")

    def test_build_bill_filename_uses_month_year_and_customer_name(self):
        consumer = {
            "billing_month": "March 2026",
            "consumer_name": "AA Cariding",
            "customer_id": "",
        }
        month_counts = {"March_2026": 2}

        filename = build_bill_filename(consumer, 1, total_consumers=2, month_counts=month_counts)

        self.assertEqual(filename, "March_2026_AA_Cariding.pdf")

    def test_generate_pdfs_per_record(self):
        template_path = "DEMONEWPDF.pdf"
        excel_path = "data.xlsx"
        if not os.path.exists(template_path) or not os.path.exists(excel_path):
            self.skipTest("Files missing")

        consumers = excel_reader.read_consumers(excel_path)
        self.assertEqual(len(consumers), 3)

        ts = template_detector.detect_template_structure(template_path)
        history = excel_reader.build_consumption_history(consumers)

        import tempfile
        with tempfile.TemporaryDirectory() as out_dir:
            generated_files = []
            for index, consumer in enumerate(consumers, start=1):
                bill = billing_engine.compute_bill(consumer)
                out_name = build_bill_filename(consumer, index, total_consumers=len(consumers), month_counts={})
                out_file = os.path.join(out_dir, out_name)
                pdf_generator.generate_bill_pdf(
                    template_path, consumer, bill, out_file,
                    consumption_history=history, template_structure=ts
                )
                self.assertTrue(os.path.exists(out_file))
                self.assertTrue(os.path.getsize(out_file) > 50000)
                generated_files.append(out_file)

            # 3 Excel rows = 3 generated PDFs
            self.assertEqual(len(generated_files), 3)

if __name__ == "__main__":
    unittest.main()

