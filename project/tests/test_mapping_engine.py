import os
import unittest
import template_detector
import mapping_engine

class MappingEngineTests(unittest.TestCase):
    def setUp(self):
        self.excel_path = "data.xlsx"
        self.template_path = "DEMONEWPDF.pdf"

    def test_mapping_analysis_valid(self):
        if not os.path.exists(self.excel_path) or not os.path.exists(self.template_path):
            self.skipTest("Required files missing")

        ts = template_detector.detect_template_structure(self.template_path)
        report = mapping_engine.analyze_mapping(self.excel_path, ts)

        self.assertTrue(report.is_valid)
        self.assertEqual(report.total_records, 3)
        self.assertIn("customer_id", report.mapped_fields)
        self.assertIn("consumer_name", report.mapped_fields)
        self.assertEqual(len(report.errors), 0)

    def test_mapping_recognizes_govt_duty_and_delay_charges_headers(self):
        excel_rows = [
            ["Customer_ID", "Consumer_Name", "Govt_Duty_Charges", "Delayed_Payment_Charges"],
            ["C001", "Test User", 94.42, 12.50],
        ]

        with open("temp_mapping_check.xlsx", "wb") as handle:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(excel_rows[0])
            ws.append(excel_rows[1])
            wb.save(handle.name)

        try:
            ts = template_detector.detect_template_structure("DEMONEWPDF.pdf")
            report = mapping_engine.analyze_mapping("temp_mapping_check.xlsx", ts)
            self.assertIn("bd_govt_duty", report.mapped_fields)
            self.assertIn("bd_delay_surcharge", report.mapped_fields)
            self.assertNotIn("Govt_Duty_Charges", report.unmapped_excel_columns)
            self.assertNotIn("Delayed_Payment_Charges", report.unmapped_excel_columns)
        finally:
            if os.path.exists("temp_mapping_check.xlsx"):
                os.remove("temp_mapping_check.xlsx")

if __name__ == "__main__":
    unittest.main()
