import unittest

from pdf_mapper import _build_chart_axis_labels, _parse_billing_month


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


if __name__ == "__main__":
    unittest.main()
