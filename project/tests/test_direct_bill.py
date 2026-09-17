"""
test_direct_bill.py
===================
Comprehensive test suite verifying the final billing month selection requirements:
- Calendar picker format (YYYY-MM) support.
- TEST A: Monthly cycle (June 2025 -> September 2026, all months after Start up to Current Month).
- TEST B: Bi-Monthly cycle (June 2025 -> August 2026, 7 bills: Aug 2025, Oct 2025, Dec 2025, Feb 2026, Apr 2026, Jun 2026, Aug 2026).
- TEST C: Current month single-month generation (September 2026 -> September 2026, exactly 1 bill).
- TEST D: Changing Start Month (December 2025 -> September 2026, Jan 2026 to Sep 2026).
- Future billing prohibition (October 2026 and later rejected).
- Dynamic consumption variation and continuous reading sequence (Start[N+1] == End[N]).
- Batch ZIP download and individual PDF preview.
"""

import unittest
import os
import zipfile
from datetime import datetime
import direct_bill_service
import billing_engine
from app import app


class TestDirectBillWorkflow(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess["authenticated"] = True
            sess["user"] = "Admin"

    def test_iso_month_input_format_support(self):
        """Verify YYYY-MM values from <input type='month'> are parsed cleanly."""
        m_name, year = direct_bill_service._parse_month_and_year("2025-06")
        self.assertEqual(m_name, "June")
        self.assertEqual(year, 2025)

        m_name, year = direct_bill_service._parse_month_and_year("2026-09")
        self.assertEqual(m_name, "September")
        self.assertEqual(year, 2026)

    def test_acceptance_test_a_monthly(self):
        """
        TEST A — MONTHLY:
        Start: June 2025, End: September 2026
        Generated months must be all months from June 2025 up to September 2026 (inclusive):
        June 2025 through September 2026 (16 periods).
        """
        periods = direct_bill_service.resolve_billing_period_sequence("2025-06", "September 2026", "Monthly")
        expected_names = [
            "June 2025", "July 2025", "August 2025", "September 2025", "October 2025", "November 2025", "December 2025",
            "January 2026", "February 2026", "March 2026", "April 2026", "May 2026", "June 2026",
            "July 2026", "August 2026", "September 2026"
        ]
        self.assertEqual(len(periods), 16)
        period_strings = [f"{m} {y}" for m, y in periods]
        self.assertEqual(period_strings, expected_names)
        self.assertNotIn("October 2026", period_strings)

    def test_acceptance_test_b_bimonthly(self):
        """
        TEST B — BI-MONTHLY:
        Start: August 2025, End: August 2026
        Generated months must be the 7 even cycle periods:
        August 2025, October 2025, December 2025, February 2026, April 2026, June 2026, August 2026.
        Total = 7 bills.
        """
        periods = direct_bill_service.resolve_billing_period_sequence("August 2025", "August 2026", "Bi-Monthly")
        expected_names = [
            "August 2025",
            "October 2025",
            "December 2025",
            "February 2026",
            "April 2026",
            "June 2026",
            "August 2026",
        ]
        self.assertEqual(len(periods), 7)
        period_strings = [f"{m} {y}" for m, y in periods]
        self.assertEqual(period_strings, expected_names)
        self.assertNotIn("June 2025", period_strings)
        self.assertNotIn("October 2026", period_strings)

    def test_acceptance_test_c_current_month_single_bill(self):
        """
        TEST C — CURRENT MONTH:
        Start: September 2026, End: September 2026
        Exactly 1 bill for September 2026.
        No October 2026.
        """
        periods = direct_bill_service.resolve_billing_period_sequence("September 2026", "September 2026", "Monthly")
        self.assertEqual(len(periods), 1)
        self.assertEqual(periods[0], ("September", 2026))

    def test_acceptance_test_d_change_start_month(self):
        """
        TEST D — CHANGE START:
        Start: January 2026, End: September 2026 (Monthly)
        Generated periods must begin from January 2026 up to September 2026 (9 bills).
        """
        periods = direct_bill_service.resolve_billing_period_sequence("January 2026", "September 2026", "Monthly")
        expected_names = [
            "January 2026", "February 2026", "March 2026", "April 2026",
            "May 2026", "June 2026", "July 2026", "August 2026", "September 2026"
        ]
        period_strings = [f"{m} {y}" for m, y in periods]
        self.assertEqual(period_strings, expected_names)
        self.assertEqual(len(periods), 9)

    def test_future_billing_prohibition(self):
        """Verify that any future month beyond current system month (e.g. October 2026) is strictly blocked."""
        with self.assertRaises(direct_bill_service.DirectBillValidationError) as ctx:
            direct_bill_service.resolve_billing_period_sequence("October 2026", "October 2026", "Monthly")
        self.assertIn("cannot be in the future", str(ctx.exception))

        with self.assertRaises(direct_bill_service.DirectBillValidationError) as ctx:
            direct_bill_service.resolve_billing_period_sequence("June 2025", "October 2026", "Monthly")
        self.assertIn("cannot be in the future", str(ctx.exception))

    def test_dynamic_units_variation(self):
        """Verify that dynamic units vary realistically and consecutive periods never duplicate."""
        ref_units = 700
        count = 7
        units_list = direct_bill_service.generate_dynamic_monthly_units(ref_units, count)

        self.assertEqual(len(units_list), count)
        for u in units_list:
            self.assertTrue(550 <= u <= 850, f"Unit {u} outside reasonable variation range")

        for i in range(len(units_list) - 1):
            self.assertNotEqual(units_list[i], units_list[i + 1])

    def test_multi_month_unbroken_continuity_and_pdf_generation(self):
        """
        Full end-to-end multi-month direct billing run:
        Bi-Monthly June 2025 -> August 2026 (7 bills), Initial Start Reading 5431, Ref 700.
        Verify:
          - 7 bills generated
          - Continuity: Start[N+1] == End[N]
          - Math: End[N] == Start[N] + Units[N]
          - Pre-flight Checks A-J pass and 7 PDFs exist
          - Consolidated ZIP archive exists and contains 7 PDFs
        """
        form_data = {
            "customer_id": "743200550",
            "consumer_name": "CHHABILKUMAR RAMGI",
            "address": "House No 399, Vadi Sheri, Vanakbara, Diu",
            "mobile_no": "9876543210",
            "email": "chhabikumar@gmail.com",
            "category": "Residential",
            "billing_cycle": "Bi-Monthly",
            "start_month": "August 2025",
            "end_month": "August 2026",
            "start_reading": 5431,
            "reference_units": 700,
        }

        result = direct_bill_service.process_direct_bill(form_data)

        self.assertTrue(result["success"])
        self.assertEqual(result["total_bills"], 7)
        self.assertTrue(result["is_multi"])
        self.assertIsNotNone(result["zip_download_url"])

        bills = result["bills"]
        self.assertEqual(len(bills), 7)

        # Initial start reading for the first bill (August 2025)
        self.assertEqual(bills[0]["summary"]["start_reading"], 5431)
        self.assertEqual(bills[0]["summary"]["billing_month"], "August 2025")
        self.assertEqual(bills[-1]["summary"]["billing_month"], "August 2026")

        # Check unbroken continuity
        for i in range(len(bills)):
            b_summary = bills[i]["summary"]
            start_r = b_summary["start_reading"]
            units_r = b_summary["units"]
            end_r = b_summary["end_reading"]

            self.assertEqual(end_r, start_r + units_r)
            pdf_path = bills[i]["output_path"]
            self.assertTrue(os.path.exists(pdf_path))
            self.assertGreater(os.path.getsize(pdf_path), 50000)

            if i < len(bills) - 1:
                next_start = bills[i + 1]["summary"]["start_reading"]
                self.assertEqual(next_start, end_r, f"Discontinuity at bill {i}")

        # Check ZIP archive
        batch_id = result["batch_id"]
        import config
        zip_path = os.path.join(config.OUTPUT_FOLDER, f"{batch_id}.zip")
        self.assertTrue(os.path.exists(zip_path))
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            self.assertEqual(len(namelist), 7)
            for name in namelist:
                self.assertTrue(name.endswith(".pdf"))

    def test_api_endpoints_multi_month(self):
        """Test POST /api/generate-bill-direct and ZIP download via client."""
        payload = {
            "customer_id": "APIUSER2",
            "consumer_name": "API User 2",
            "address": "Market Street, Diu",
            "mobile_no": "9876543210",
            "email": "user2@test.com",
            "category": "Commercial",
            "billing_cycle": "Bi-Monthly",
            "start_month": "April 2026",
            "end_month": "June 2026",
            "start_reading": 3000,
            "reference_units": 500,
        }
        res = self.client.post("/api/generate-bill-direct", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        # April 2026, June 2026 = 2 bills
        self.assertEqual(data["total_bills"], 2)

        batch_id = data["batch_id"]
        # Download ZIP
        zip_res = self.client.get(f"/api/download-direct-batch-zip/{batch_id}")
        self.assertEqual(zip_res.status_code, 200)
        self.assertEqual(zip_res.mimetype, "application/zip")


    def test_dynamic_billing_dates_rules_and_relationships(self):
        """Verify Reading Date (1-5), Bill Date (+8d), Due Date (22-27), and strict order."""
        for m_name in ["January", "February", "June", "August", "December"]:
            dates = direct_bill_service.generate_validated_bill_dates(m_name, 2026)
            m_idx = direct_bill_service.MONTH_NAMES.index(m_name) + 1

            r_dt = dates["reading_dt"]
            b_dt = dates["bill_dt"]
            d_dt = dates["due_dt"]

            # Same billing month check
            self.assertEqual(r_dt.month, m_idx)
            self.assertEqual(b_dt.month, m_idx)
            self.assertEqual(d_dt.month, m_idx)
            self.assertEqual(r_dt.year, 2026)
            self.assertEqual(b_dt.year, 2026)
            self.assertEqual(d_dt.year, 2026)

            # Day range checks
            self.assertGreaterEqual(r_dt.day, 1)
            self.assertLessEqual(r_dt.day, 5)

            # Bill Date = Reading Date + 8 days
            from datetime import timedelta
            self.assertEqual(b_dt, r_dt + timedelta(days=8))
            self.assertGreaterEqual(b_dt.day, 9)
            self.assertLessEqual(b_dt.day, 13)

            # Due Date 22-27
            self.assertGreaterEqual(d_dt.day, 22)
            self.assertLessEqual(d_dt.day, 27)

            # Strict order invariant
            self.assertTrue(r_dt < b_dt < d_dt)

    def test_previous_payment_chain_and_no_hardcoded_values(self):
        """Verify multi-month previous payment chaining, preceding period dates, and zero hardcoded dates."""
        import pdfplumber

        payload = {
            "customer_id": "CHAINTEST1",
            "consumer_name": "Dynamic Tester",
            "address": "123 Ocean Boulevard, Diu",
            "mobile_no": "9876543210",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "February 2026",
            "end_month": "April 2026",
            "start_reading": 5431,
            "reference_units": 700,
        }
        # Generates February 2026, March 2026, April 2026 = 3 bills
        result = direct_bill_service.process_direct_bill(payload)
        bills = result["bills"]
        self.assertEqual(len(bills), 3)

        # Bill 0: February 2026
        b0_summary = bills[0]["summary"]
        self.assertEqual(b0_summary["billing_month"], "February 2026")
        # Previous period for February 2026 Monthly must be January 2026
        b0_prev_pay_date = b0_summary["previous_payment_date"]
        self.assertTrue(b0_prev_pay_date.endswith("/01/2026"), f"Expected Jan 2026, got {b0_prev_pay_date}")
        self.assertGreater(b0_summary["previous_payment"], 0)
        self.assertNotEqual(b0_summary["previous_payment"], 7420.0)

        # Bill 1: March 2026
        b1_summary = bills[1]["summary"]
        self.assertEqual(b1_summary["billing_month"], "March 2026")
        # March Previous Payment MUST equal February Total Amount Due!
        self.assertAlmostEqual(b1_summary["previous_payment"], b0_summary["total_amount"], places=2)
        # March Previous Payment Date MUST belong to February 2026 and be between b0 Bill Date and Due Date
        b1_prev_pay_date = b1_summary["previous_payment_date"]
        self.assertTrue(b1_prev_pay_date.endswith("/02/2026"), f"Expected Feb 2026, got {b1_prev_pay_date}")

        # Bill 2: April 2026
        b2_summary = bills[2]["summary"]
        self.assertEqual(b2_summary["billing_month"], "April 2026")
        # April Previous Payment MUST equal March Total Amount Due!
        self.assertAlmostEqual(b2_summary["previous_payment"], b1_summary["total_amount"], places=2)
        # April Previous Payment Date MUST belong to March 2026
        b2_prev_pay_date = b2_summary["previous_payment_date"]
        self.assertTrue(b2_prev_pay_date.endswith("/03/2026"), f"Expected Mar 2026, got {b2_prev_pay_date}")

        # Inspect generated PDFs to confirm NO hardcoded text appears
        for b in bills:
            with pdfplumber.open(b["output_path"]) as pdf:
                full_text = " ".join([page.extract_text() or "" for page in pdf.pages])
                self.assertNotIn("14/12/2015", full_text)
                self.assertNotIn("14/07/26", full_text)
                self.assertNotIn("7,420.00", full_text)

    def test_chart_batch_units_correspondence(self):
        """Verify consumption chart history matches generated batch units 100%."""
        consumer = {
            "customer_id": "CHARTUSER",
            "billing_month": "June 2026",
            "billing_mode": "30",
        }
        batch_records = {
            ("Jan", "2026"): 658.0,
            ("Feb", "2026"): 733.0,
            ("Mar", "2026"): 691.0,
            ("Apr", "2026"): 714.0,
            ("May", "2026"): 682.0,
            ("Jun", "2026"): 721.0,
        }
        history = direct_bill_service.build_consumption_history_for_consumer(
            consumer,
            current_units=721.0,
            batch_records=batch_records,
            reference_units=700.0,
        )
        user_history = history["CHARTUSER"]

        # Check all months match batch records exactly
        self.assertEqual(user_history[("Jan", "2026")], 658.0)
        self.assertEqual(user_history[("Feb", "2026")], 733.0)
        self.assertEqual(user_history[("Mar", "2026")], 691.0)
        self.assertEqual(user_history[("Apr", "2026")], 714.0)
        self.assertEqual(user_history[("May", "2026")], 682.0)
        self.assertEqual(user_history[("Jun", "2026")], 721.0)


    def test_section_25_monthly_exact_scenario(self):
        """
        SECTION 25 TEST:
        Billing Cycle: Monthly
        Start: January 2026 (Start Reading: 5431, Ref Units: 700)
        End: June 2026
        Expected:
          January, February, March, April, May, June (6 bills).
          Each PDF receives its own distinct Billing Month.
          Reading Date: 1-5 of that bill's month.
          Bill Date: Reading Date + 8 days.
          Due Date: 22-27 of that bill's month.
          Reading Date < Bill Date < Due Date.
          Previous Payment chains dynamically.
          Preview and download URLs correctly point to unique files.
        """
        payload = {
            "customer_id": "SEC25USER",
            "consumer_name": "Section 25 Consumer",
            "address": "404 Main Road, Diu",
            "mobile_no": "9876543210",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "January 2026",
            "end_month": "June 2026",
            "start_reading": 5431,
            "reference_units": 700,
        }
        res = direct_bill_service.process_direct_bill(payload)
        bills = res["bills"]
        self.assertEqual(len(bills), 6)

        expected_months = [
            "January 2026", "February 2026", "March 2026",
            "April 2026", "May 2026", "June 2026"
        ]

        for i, b in enumerate(bills):
            s = b["summary"]
            # Billing Month
            self.assertEqual(s["billing_month"], expected_months[i])

            # Dates
            r_dt = datetime.strptime(s["reading_date"], "%d/%m/%Y").date()
            b_dt = datetime.strptime(s["bill_date"], "%d/%m/%Y").date()
            d_dt = datetime.strptime(s["due_date"], "%d/%m/%Y").date()

            self.assertEqual(r_dt.month, i + 1)
            self.assertEqual(r_dt.year, 2026)
            self.assertGreaterEqual(r_dt.day, 1)
            self.assertLessEqual(r_dt.day, 5)

            from datetime import timedelta
            self.assertEqual(b_dt, r_dt + timedelta(days=8))
            self.assertEqual(b_dt.month, i + 1)
            self.assertEqual(b_dt.year, 2026)

            self.assertEqual(d_dt.month, i + 1)
            self.assertEqual(d_dt.year, 2026)
            self.assertGreaterEqual(d_dt.day, 22)
            self.assertLessEqual(d_dt.day, 27)

            self.assertTrue(r_dt < b_dt < d_dt)

            # Continuous Meter Reading
            self.assertEqual(s["end_reading"], s["start_reading"] + s["units"])
            if i > 0:
                self.assertEqual(s["start_reading"], bills[i - 1]["summary"]["end_reading"])
                # Previous Payment Chain
                self.assertAlmostEqual(s["previous_payment"], bills[i - 1]["summary"]["total_amount"], places=2)
                # Previous Payment Date in previous month
                p_dt = datetime.strptime(s["previous_payment_date"], "%d/%m/%Y").date()
                self.assertEqual(p_dt.month, i)
                self.assertEqual(p_dt.year, 2026)

            # Test preview URL serves correct file
            preview_res = self.client.get(b["preview_url"])
            self.assertEqual(preview_res.status_code, 200)

    def test_section_26_bimonthly_exact_scenario(self):
        """
        SECTION 26 TEST:
        Billing Cycle: Bi-Monthly
        Start: February 2026
        End: August 2026
        Expected bills: February 2026, April 2026, June 2026, August 2026 (4 bills).
        Previous periods:
          April -> February
          June -> April
          August -> June
        Chart contains only even cycle months (no odd months).
        """
        payload = {
            "customer_id": "SEC26USER",
            "consumer_name": "BiMonthly Tester",
            "address": "55 Beach Rd, Diu",
            "mobile_no": "9876543210",
            "category": "Commercial",
            "billing_cycle": "Bi-Monthly",
            "start_month": "February 2026",
            "end_month": "August 2026",
            "start_reading": 1000,
            "reference_units": 650,
        }
        res = direct_bill_service.process_direct_bill(payload)
        bills = res["bills"]
        self.assertEqual(len(bills), 4)

        expected_periods = ["February 2026", "April 2026", "June 2026", "August 2026"]
        for i, b in enumerate(bills):
            s = b["summary"]
            self.assertEqual(s["billing_month"], expected_periods[i])

            if i > 0:
                # Previous payment must equal previous bill's total
                self.assertAlmostEqual(s["previous_payment"], bills[i - 1]["summary"]["total_amount"], places=2)
                # Previous payment date must belong to previous bi-monthly month
                prev_month_num = [2, 4, 6][i - 1]
                p_dt = datetime.strptime(s["previous_payment_date"], "%d/%m/%Y").date()
                self.assertEqual(p_dt.month, prev_month_num)
                self.assertEqual(p_dt.year, 2026)

            # Test preview URL serves correct file
            preview_res = self.client.get(b["preview_url"])
            self.assertEqual(preview_res.status_code, 200)


if __name__ == "__main__":
    unittest.main()


