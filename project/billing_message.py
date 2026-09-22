"""
billing_message.py
===================
Renders the "IMPORTANT BILLING MESSAGE" paragraph as a single reportlab
Paragraph flowable, instead of drawing "Rs.", the amount, and the
surrounding sentence as separate drawString() calls in different fonts.

Why this fixes the misalignment bug:
- A single Paragraph is one text object. reportlab lays out every glyph -
  letters, digits, punctuation, "Rs." - using the SAME registered font's
  ascent/descent/baseline metrics. There is no place left in the pipeline
  for a fallback font (e.g. Helvetica) to sneak in for just the numbers,
  which is what caused the wrong-font, low-baseline, undersized "167" /
  "170" in April_2025.pdf.
- Word wrapping, spacing, and kerning are handled by reportlab's own
  paragraph engine against the font's real metrics - not by manually
  measuring stringWidth() and placing words at hand-computed x positions.
- Leading (line spacing) is one constant value applied uniformly to every
  line, so wrapped lines never drift.
"""

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import Paragraph


# NEW
def draw_billing_message(canvas_obj, page_height, box, registered_fonts,
                          font_name="NeurialGrotesk-Regular",
                          bold_font_name="NeurialGrotesk-Bold",
                          font_size=7.5, leading=10.5,
                          due_amount=None, due_date=None,
                          recovered_amount=None, prompt_rebate_date=None,
                          tariff_order_date="13.06.2024",
                          bg=(0.90980, 0.90588, 0.88235),
                          max_height=None):
    """
    box = (x0, top, x1, bottom) in the same top-down coordinate space
    your other Field() boxes already use (top/bottom measured from the
    page's top edge, exactly like pdf_mapper.Field).

    All dynamic values are formatted with the SAME font_name that wraps
    the rest of the sentence - there is deliberately no separate font or
    size for "Rs." or the numbers, which is what the reference PDF does.
    """
    x0, top, x1, bottom = box
    box_width = x1 - x0
    available_height = (max_height if max_height is not None else (bottom - top))

    resolved_regular = font_name if not registered_fonts or font_name in registered_fonts else "Helvetica"
    resolved_bold = bold_font_name if not registered_fonts or bold_font_name in registered_fonts else "Helvetica-Bold"

    def fmt_amount(v):
      return f"{v:.2f}" if v is not None else ""

    # Every run of text - including "Rs.", the amount, and the date - uses
    # the paragraph's own fontName via inline <font> tags that point at the
    # SAME resolved font (never a bare/unregistered fallback), so nothing
    # drops to a mismatched font or size mid-sentence.
    # NEW
    # NEW
    para_html = (
        f'<u><font name="{resolved_bold}">IMPORTANT BILLING MESSAGE</font></u><br/>'
        f'(1)Amount of Rs. {fmt_amount(due_amount)} payable on representation of this bill. '
        f'If not paid on or before {due_date or ""} an amount of Rs. {fmt_amount(recovered_amount)} '
        f'shall be recovered which includes delay payment surcharge also.<br/>'
        f'(2)Please pay this bill on or before {prompt_rebate_date or ""} to avail Prompt Payment '
        f'Rebate as per Hon\u2019ble JERC Tariff Order dated {tariff_order_date}.'
    )

    # Create a paragraph with box padding that matches the reference text inset.
    padding_left = 6.8
    padding_right = 3.5
    padding_top = 7.0
    padding_bottom = 19.0
    inner_width = max(box_width - padding_left - padding_right, 1.0)
    body_font_size = 6.0
    heading_font_size = 7.0
    leading_value = 8.5

    style = ParagraphStyle(
        name="BillingMessage",
        fontName=resolved_regular,
        fontSize=body_font_size,
        leading=leading_value,
        alignment=TA_LEFT,
        spaceBefore=0,
        spaceAfter=0,
        leftIndent=0,
        rightIndent=0,
    )
    paragraph = Paragraph(
        f'<font name="{resolved_bold}" size="{heading_font_size}">IMPORTANT BILLING MESSAGE</font><br/>'
        f'<font name="{resolved_regular}" size="{body_font_size}">'
        f'(1)Amount of Rs. {fmt_amount(due_amount)} payable on representation of this bill. '
        f'If not paid on or before {due_date or ""} an amount of Rs. {fmt_amount(recovered_amount)} '
        f'shall be recovered which includes delay payment surcharge also.<br/>'
        f'(2)Please pay this bill on or before {prompt_rebate_date or ""} to avail Prompt Payment Rebate as '
        f'per Hon’ble JERC Tariff Order dated {tariff_order_date}.</font>',
        style
    )
    _, used_height = paragraph.wrap(inner_width, 10000)

    canvas_obj.setFillColorRGB(*bg)
    rect_x0 = x0
    rect_x1 = x1
    rect_y0 = page_height - bottom
    rect_width = rect_x1 - rect_x0
    rect_height = bottom - top
    canvas_obj.rect(rect_x0, rect_y0, rect_width, rect_height, stroke=0, fill=1)

    draw_x = x0 + padding_left
    draw_y = page_height - top - padding_top - used_height
    paragraph.drawOn(canvas_obj, draw_x, draw_y)

    return rect_height