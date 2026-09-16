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


if __name__ == "__main__":
    unittest.main()

