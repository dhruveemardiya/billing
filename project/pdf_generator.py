import io
import os

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from billing_message import draw_billing_message
import font_manager
import pdf_mapper


def _resolve_font_name(requested_font: str, registered_fonts: dict) -> str:
    if not registered_fonts:
        return requested_font

    if requested_font == "Helvetica-Bold":
        return "NeurialGrotesk-Bold" if "NeurialGrotesk-Bold" in registered_fonts else requested_font
    if requested_font == "Helvetica":
        return "NeurialGrotesk-Regular" if "NeurialGrotesk-Regular" in registered_fonts else requested_font
    if requested_font.startswith("Helvetica"):
        return next(
            (name for name in ("NeurialGrotesk-Medium", "NeurialGrotesk-Regular") if name in registered_fonts),
            requested_font,
        )
    return requested_font
def _build_page_overlay(page_width, page_height, fields, values, registered_fonts):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))

    # Pass 1: draw every field's background rectangle first, before any
    # text. Doing backgrounds in their own pass guarantees a later field's
    # rectangle can never paint over an earlier field's descenders (e.g.
    # address_line1's rect was clipping the tail off consumer_name's comma,
    # since the two boxes sit only ~2pt apart).
    for field in fields:
        if field.key == "billing_message_box":
            # Its background is drawn separately, sized to the wrapped
            # paragraph's real height (see the billing_message_box block
            # below) instead of this fixed field.top/field.bottom rect.
            continue
        x1 = field.x1 if field.x1 is not None else field.x0 + 150
        rect_x0 = field.x0 - field.pad
        rect_x1 = x1 + field.pad
        rect_y0 = page_height - field.bottom - field.pad
        rect_y1 = page_height - field.top + field.pad
        c.setFillColorRGB(*field.bg)
        c.rect(rect_x0, rect_y0, rect_x1 - rect_x0, rect_y1 - rect_y0, stroke=0, fill=1)

        # The consumption_sentence_units field's bottom bound sits ~1.2pt
        # above the template's actual baseline for "87 units" (measured
        # directly off demo.pdf), so even with the standard pad the mask
        # stops about 2pt short of the real glyph bottoms. That uncovered
        # sliver of the original bold text was showing through as a thin
        # black line under the new value. Widen the mask downward only
        # (not left/right) so we don't eat into the neighboring "this".
        if field.key == "consumption_sentence_units":
            extra_bottom = 2.0
            c.setFillColorRGB(*field.bg)
            c.rect(rect_x0, rect_y0 - extra_bottom, rect_x1 - rect_x0,
                   (rect_y1 - rect_y0) + extra_bottom, stroke=0, fill=1)

    # Pass 2: draw all text on top, now that every background is already down.
    for field in fields:
        text = values.get(field.key, "")
        if text is None:
            text = ""
        text = str(text)
        if not text:
            continue

        x1 = field.x1 if field.x1 is not None else field.x0 + 150

        c.setFillColorRGB(0, 0, 0)
        resolved_font = _resolve_font_name(field.font, registered_fonts)
        font_size = field.size
        max_width = x1 - field.x0
        while font_size > 5.0 and c.stringWidth(text, resolved_font, font_size) > max_width:
            font_size -= 0.5
        c.setFont(resolved_font, font_size)
        baseline_y = page_height - field.bottom

        is_bold_field = "Bold" in field.font or "Extrabold" in field.font
        has_rupee = text.startswith("₹")

        if field.align == "right":
            c.drawRightString(x1, baseline_y, text)
        elif field.align == "center":
            c.drawCentredString((field.x0 + x1) / 2, baseline_y, text)
        else:
            if has_rupee:
                # Draw the rupee glyph separately: its internal metrics sit
                # higher/smaller than the digit glyphs, so nudge it down to
                # visually sit on the same baseline as the numbers, and
                # fake-bold it (double-strike) to match the bold digit weight.
                rest_of_text = text[1:]
                rupee_y = baseline_y - font_size * 0.06  # nudge down onto baseline
                rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else resolved_font
                c.setFont(rupee_font, font_size)
                if is_bold_field:
                    for dx in (-0.6, -0.3, 0.3, 0.6):
                        c.drawString(field.x0 + dx, rupee_y, "₹")
                    c.drawString(field.x0, rupee_y, "₹")
                else:
                    c.drawString(field.x0, rupee_y, "₹")
                rupee_width = c.stringWidth("₹", rupee_font, font_size)
                c.setFont(resolved_font, font_size)
                c.drawString(field.x0 + rupee_width, baseline_y, rest_of_text)
                rupee_width = c.stringWidth("₹", rupee_font, font_size)
                c.setFont(resolved_font, font_size)
                c.drawString(field.x0 + rupee_width, baseline_y, rest_of_text)
            else:
                c.drawString(field.x0, baseline_y, text)
    if any(f.key == "meter_no" for f in fields):
        # The meter-details box is an octagon (corners cut diagonally).
        # The consumption_units field's background rectangle sits right up
        # against the bottom-right cut and slightly overlaps that diagonal
        # border line, painting a tiny sliver of it over with the cream
        # background. Redraw that segment so the border reads as one
        # continuous line again, matching the original template artwork.
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.7)
        c.line(109.5, page_height - 502.8, 118.5, page_height - 493.8)

    if any(f.key == "donut_total_charges" for f in fields):
        sx0, stop, sx1, sbottom = (41.0, 530.0, 300.0, 684.0)
        c.setFillColorRGB(*pdf_mapper.CREAM_BG)
        c.rect(sx0, page_height - sbottom, sx1 - sx0, sbottom - stop, stroke=0, fill=1)
        from reportlab.lib.utils import ImageReader
        ad_image = ImageReader("static/images/rccb_ad1.png")
        c.drawImage(ad_image, sx0, page_height - sbottom, sx1 - sx0, sbottom - stop,
                    preserveAspectRatio=True, anchor='n', mask='auto')

        # Leader line connecting the donut chart to the "Energy Charges" label
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.3)
        c.line(370.02, page_height - 435.07, 387.28, page_height - 435.07)

        CHART_AXIS_Y = 679.49
        CHART_PT_PER_UNIT = 0.2
        PRIOR_YEAR_COLOR = (0.827, 0.827, 0.827)   # light gray - matches demo.pdf
        CURRENT_YEAR_COLOR = (0.55, 0.55, 0.55)    # medium gray - matches demo.pdf
        HIGHLIGHT_COLOR = (0.15, 0.15, 0.15)       # near-black - the current billing month only
        CHART_CLEAR_TOP = 590
        CHART_CLEAR_X0, CHART_CLEAR_X1 = 316.0, 545.0
        BAR_X_POSITIONS = [
            (318.11, 333.11), (333.11, 348.11),
            (357.11, 372.11), (372.11, 387.11),
            (396.11, 411.11), (411.11, 426.11),
            (435.11, 450.11), (450.11, 465.11),
            (474.11, 489.11), (489.11, 504.11),
            (513.11, 528.11), (528.11, 543.11),
        ]

        chart_values = values.get("chart_values", [])

        # Scale so the tallest bar in THIS bill always fills the same
        # proportion of the box that 288 units fills in demo.pdf (~65%),
        # instead of using a fixed pt-per-unit that only looks right when
        # the max value in the data happens to be close to 288. Without
        # this, bills whose tallest bar is smaller than demo.pdf's leave a
        # big empty gap above the bars and below the axis labels (and
        # bills with a taller max value can crowd/clip against the top).
        max_chart_height = CHART_AXIS_Y - CHART_CLEAR_TOP
        _valid_vals = [float(v) for v in chart_values if v is not None]
        _tallest = max(_valid_vals) if _valid_vals else 0
        TARGET_FILL_RATIO = 0.65
        chart_pt_per_unit = (
            (max_chart_height * TARGET_FILL_RATIO / _tallest)
            if _tallest > 0 else CHART_PT_PER_UNIT
        )

        c.setFillColorRGB(*pdf_mapper.CREAM_BG)
        c.rect(CHART_CLEAR_X0, page_height - CHART_AXIS_Y,
               CHART_CLEAR_X1 - CHART_CLEAR_X0, CHART_AXIS_Y - CHART_CLEAR_TOP,
               stroke=0, fill=1)

        for i, raw_value in enumerate(chart_values):
            if raw_value is None or i >= len(BAR_X_POSITIONS):
                continue
            try:
                value_num = float(raw_value)
            except (TypeError, ValueError):
                continue

            bar_x0, bar_x1 = BAR_X_POSITIONS[i]
            bar_height = min(value_num * chart_pt_per_unit, CHART_AXIS_Y - CHART_CLEAR_TOP)

            if i == len(BAR_X_POSITIONS) - 1:
                bar_color = HIGHLIGHT_COLOR       # last slot = current billing month, highlighted
            elif i % 2 == 0:
                bar_color = PRIOR_YEAR_COLOR       # even index = prior-year bar
            else:
                bar_color = CURRENT_YEAR_COLOR     # odd index = current-year bar

            c.setFillColorRGB(*bar_color)
            c.rect(bar_x0, page_height - CHART_AXIS_Y, bar_x1 - bar_x0, bar_height, stroke=0, fill=1)

            bar_top_from_axis = CHART_AXIS_Y - bar_height
            # Always sit the label a fixed 4pt above THIS bar's own top.
            # (No longer clamped to CHART_CLEAR_TOP + 5 - that clamp was
            # from the old fixed-scale code and, combined with the new
            # dynamic scaling, was pinning short bars' labels way up near
            # the top of the box instead of near their bars.)
            label_bottom_topcoord = bar_top_from_axis - 4.0
            c.setFillColorRGB(0, 0, 0)
            c.setFont(_resolve_font_name("NeurialGrotesk-Regular", registered_fonts), 5)
            c.drawCentredString((bar_x0 + bar_x1) / 2, page_height - label_bottom_topcoord, str(int(value_num)))
            
        
    if any(f.key == "billing_message_box" for f in fields):
        box_field = next(f for f in fields if f.key == "billing_message_box")
        draw_billing_message(
            c, page_height,
            box=(box_field.x0, box_field.top, box_field.x1, box_field.bottom),
            registered_fonts=registered_fonts,
            due_amount=values.get("_bill_total_amount_due"),
            due_date=values.get("due_by_date"),
            recovered_amount=values.get("_bill_amount_after_due_date"),
            prompt_rebate_date=values.get("due_by_date"),
            bg=box_field.bg,
            max_height=box_field.bottom - box_field.top,
        )

    c.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]

def generate_bill_pdf(template_path: str, consumer: dict, bill, output_path: str, consumption_history: dict = None) -> str:
    values = pdf_mapper.build_field_values(consumer, bill, consumption_history=consumption_history)

    reader = PdfReader(template_path)
    registered_fonts = font_manager.ensure_template_fonts_registered(template_path)
    writer = PdfWriter()

    fields_by_page = {}
    for field in pdf_mapper.ALL_FIELDS:
        fields_by_page.setdefault(field.page, []).append(field)

    for page_index, page in enumerate(reader.pages):
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        page_fields = fields_by_page.get(page_index, [])
        if page_fields:
            overlay_page = _build_page_overlay(page_width, page_height, page_fields, values, registered_fonts)
            page.merge_page(overlay_page)

        writer.add_page(page)

    output_dir = os.path.dirname(output_path) or "."
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path