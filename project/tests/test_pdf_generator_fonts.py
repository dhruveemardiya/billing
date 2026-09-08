import unittest

from pdf_generator import _resolve_font_name


class PdfGeneratorFontSelectionTests(unittest.TestCase):
    def test_prefers_template_bold_font_for_bold_requests(self):
        registered_fonts = {
            "NeurialGrotesk-Regular": True,
            "NeurialGrotesk-Bold": True,
            "NeurialGrotesk-Medium": True,
        }
        self.assertEqual(
            _resolve_font_name("Helvetica-Bold", registered_fonts),
            "NeurialGrotesk-Bold",
        )

    def test_prefers_template_regular_font_for_standard_requests(self):
        registered_fonts = {
            "NeurialGrotesk-Regular": True,
            "NeurialGrotesk-Bold": True,
        }
        self.assertEqual(
            _resolve_font_name("Helvetica", registered_fonts),
            "NeurialGrotesk-Regular",
        )

    def test_falls_back_to_requested_font_when_no_match_exists(self):
        self.assertEqual(_resolve_font_name("Helvetica-Bold", {"Arial": True}), "Helvetica-Bold")


if __name__ == "__main__":
    unittest.main()
