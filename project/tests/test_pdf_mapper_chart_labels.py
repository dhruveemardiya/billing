import unittest

from pdf_mapper import _build_chart_axis_labels, _parse_billing_month, compute_donut_component_data, build_field_values
from billing_engine import BillCalculation


class PdfMapperChartAxisTests(unittest.TestCase):
    def test_build_chart_axis_labels_returns_last_six_months(self):
        months, years, current_month, current_year = _build_chart_axis_labels("Feb 2025", groups=6)

        self.assertEqual(months, ["Sep", "Oct", "Nov", "Dec", "Jan", "Feb"])
        self.assertEqual(years, ["2023", "2024", "2023", "2024", "2023", "2024", "2023", "2024", "2024", "2025", "2024", "2025"])
        self.assertEqual(current_month, "Feb")
        self.assertEqual(current_year, "2025")

    def test_parse_billing_month_handles_numeric_month_year(self):
        self.assertEqual(_parse_billing_month("03 2024"), ("Mar", "2024"))
        self.assertEqual(_parse_billing_month("3/24"), ("Mar", "2024"))
        self.assertEqual(_parse_billing_month("September 2024"), ("Sep", "2024"))

    def test_parse_billing_month_returns_empty_if_invalid(self):
        self.assertEqual(_parse_billing_month(""), ("", ""))
        self.assertEqual(_parse_billing_month(None), ("", ""))

    def test_compute_donut_component_data_uses_actual_amounts_and_total(self):
        data = compute_donut_component_data(
            fixed_charges=55.00,
            energy_charges=370.00,
            fppca_charges=47.09,
            government_duty=94.42,
        )

        self.assertAlmostEqual(data["total"], 566.51)
        self.assertAlmostEqual(sum(item["amount"] for item in data["components"]), 566.51)
        self.assertAlmostEqual(data["components"][0]["angle"], (55.00 / 566.51) * 360)
        self.assertAlmostEqual(data["components"][1]["angle"], (94.42 / 566.51) * 360)
        self.assertAlmostEqual(data["components"][2]["angle"], (47.09 / 566.51) * 360)
        self.assertAlmostEqual(data["components"][3]["angle"], (370.00 / 566.51) * 360)

    def test_headline_due_amount_and_previous_payment_line_rounded_with_decimals(self):
        consumer = {
            "customer_id": "743200550",
            "previous_payment": 809.05,
            "previous_payment_date": "20/06/2026",
            "billing_month": "August 2026",
        }
        bill = BillCalculation(
            sanctioned_load_kw=1.0,
            units_consumed=244.0,
            category_key="residential",
            energy_charges=564.99,
            fixed_charges=55.00,
            fppca_charges=68.07,
            govt_duty=103.21,
            total_amount_due=791.27,
        )
        values = build_field_values(consumer, bill)
        self.assertEqual(values["headline_due_amount"], "791.00")
        self.assertEqual(
            values["previous_payment_line"],
            "Thank you for your previous payment of ₹ 809.00 on 20/06/2026 ."
        )

    def test_dynamic_chart_fallback_values_around_reference_units(self):
        consumer = {
            "customer_id": "743200550",
            "billing_month": "August 2026",
            "reference_units": 700,
        }
        bill = BillCalculation(
            sanctioned_load_kw=1.0,
            units_consumed=715.0,
            category_key="residential",
            energy_charges=564.99,
            fixed_charges=55.00,
            fppca_charges=68.07,
            govt_duty=103.21,
            total_amount_due=791.27,
        )
        values = build_field_values(consumer, bill)
        chart_vals = values["chart_values"]
        # Exactly 12 values (6 pairs)
        self.assertEqual(len(chart_vals), 12)
        # The current bill's units consumed must be at the final current cycle slot
        self.assertEqual(chart_vals[-1], 715.0)
        # All preceding current cycle slots (odd indices) must be populated with realistic dynamic units around 700
        for i in range(1, 11, 2):
            self.assertIsNotNone(chart_vals[i])
            self.assertGreater(chart_vals[i], 0)
            # Realistic units around 700 (within +-25%)
            self.assertTrue(500 <= chart_vals[i] <= 900)

    def test_direct_bill_chart_mapping_single_and_batch(self):
        import direct_bill_service
        # 1. Single bill test
        res1 = direct_bill_service.process_direct_bill({
            "customer_id": "CHARTTEST1",
            "consumer_name": "Chart Test 1",
            "address": "101 Ocean Ave, Diu",
            "mobile_no": "9876543210",
            "category": "Residential",
            "billing_cycle": "Monthly",
            "start_month": "March 2026",
            "end_month": "March 2026",
            "start_reading": 5000,
            "reference_units": 700,
        })
        b1 = res1["bills"][0]
        m_labels1 = b1["consumer"]["chart_month_labels"]
        vals1 = b1["consumer"]["chart_values"]
        self.assertEqual(m_labels1, ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"])
        self.assertEqual(len(vals1), 12)
        # Rightmost bar (index 11) is the current bill's actual generated units
        self.assertEqual(vals1[11], b1["consumer"]["units"])
        self.assertEqual(b1["consumer"]["highlight_bar_index"], 11)

        # 2. Two bi-monthly bills test
        res2 = direct_bill_service.process_direct_bill({
            "customer_id": "CHARTTEST2",
            "consumer_name": "Chart Test 2",
            "address": "102 Ocean Ave, Diu",
            "mobile_no": "9876543210",
            "category": "Residential",
            "billing_cycle": "Bi-Monthly",
            "start_month": "February 2025",
            "end_month": "April 2025",
            "start_reading": 5000,
            "reference_units": 700,
        })
        bills2 = res2["bills"]
        self.assertEqual(len(bills2), 2)
        # Bill 0 (Feb 2025) has Feb as the rightmost group
        m_labels_b0 = bills2[0]["consumer"]["chart_month_labels"]
        self.assertEqual(m_labels_b0, ["Apr", "Jun", "Aug", "Oct", "Dec", "Feb"])
        vals_b0 = bills2[0]["consumer"]["chart_values"]
        self.assertEqual(len(vals_b0), 12)
        self.assertEqual(vals_b0[11], bills2[0]["consumer"]["units"])
        self.assertEqual(bills2[0]["consumer"]["highlight_bar_index"], 11)

        # Bill 1 (Apr 2025) has Apr as the rightmost group
        m_labels_b1 = bills2[1]["consumer"]["chart_month_labels"]
        self.assertEqual(m_labels_b1, ["Jun", "Aug", "Oct", "Dec", "Feb", "Apr"])
        vals_b1 = bills2[1]["consumer"]["chart_values"]
        self.assertEqual(len(vals_b1), 12)
        self.assertEqual(vals_b1[11], bills2[1]["consumer"]["units"])
        # Bill 1's preceding group (Feb 2025 at index 9) matches Bill 0's actual generated units
        self.assertEqual(vals_b1[9], bills2[0]["consumer"]["units"])
        self.assertEqual(bills2[1]["consumer"]["highlight_bar_index"], 11)


if __name__ == "__main__":
    unittest.main()


