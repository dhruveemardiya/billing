import io
import math
import os
from typing import Optional

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, ContentStream
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from billing_message import draw_billing_message
import font_manager
import pdf_mapper
from template_detector import detect_template_structure, TemplateStructure, Field


def _resolve_font_name(requested_font: str, registered_fonts: dict) -> str:
    if not registered_fonts:
        return requested_font
    if requested_font in registered_fonts:
        return requested_font

    # Check Manrope family matches
    if requested_font.startswith("Manrope"):
        if "ExtraBold" in requested_font:
            return next((n for n in ("Manrope-ExtraBold", "Manrope-Bold") if n in registered_fonts), requested_font)
        if "Bold" in requested_font:
            return next((n for n in ("Manrope-Bold", "Manrope-ExtraBold") if n in registered_fonts), requested_font)
        if "Medium" in requested_font:
            return next((n for n in ("Manrope-Medium", "Manrope-Regular") if n in registered_fonts), requested_font)
        if "Regular" in requested_font:
            return "Manrope-Regular" if "Manrope-Regular" in registered_fonts else requested_font

    # Check NeurialGrotesk family matches
    if requested_font.startswith("Neurial"):
        if "Extrabold" in requested_font:
            return next((n for n in ("NeurialGrotesk-Extrabold", "NeurialGrotesk-Bold") if n in registered_fonts), requested_font)
        if "Bold" in requested_font:
            return "NeurialGrotesk-Bold" if "NeurialGrotesk-Bold" in registered_fonts else requested_font
        if "Medium" in requested_font:
            return next((n for n in ("NeurialGrotesk-Medium", "NeurialGrotesk-Regular") if n in registered_fonts), requested_font)
        return "NeurialGrotesk-Regular" if "NeurialGrotesk-Regular" in registered_fonts else requested_font

    # Generic Helvetica mappings
    if requested_font == "Helvetica-Bold":
        for cand in ("Manrope-Bold", "NeurialGrotesk-Bold", "Manrope-ExtraBold"):
            if cand in registered_fonts:
                return cand
        return requested_font
    if requested_font == "Helvetica":
        for cand in ("Manrope-Regular", "NeurialGrotesk-Regular"):
            if cand in registered_fonts:
                return cand
        return requested_font

    # Fallbacks based on weight
    if "Bold" in requested_font or "Extrabold" in requested_font:
        for cand in ("Manrope-Bold", "NeurialGrotesk-Bold", "Manrope-ExtraBold"):
            if cand in registered_fonts:
                return cand
    if "Medium" in requested_font:
        for cand in ("Manrope-Medium", "NeurialGrotesk-Medium", "Manrope-Regular"):
            if cand in registered_fonts:
                return cand
    for cand in ("Manrope-Regular", "NeurialGrotesk-Regular"):
        if cand in registered_fonts:
            return cand

    return requested_font


def _strip_template_donut_and_leaders(page, reader):
    """Remove static background donut arcs and leader lines from the template PDF page content stream."""
    contents_obj = page.get("/Contents")
    if not contents_obj:
        return
    contents_obj = contents_obj.get_object()
    stream = ContentStream(contents_obj, reader)

    new_ops = []
    for operands, op in stream.operations:
        op_str = op.decode() if isinstance(op, bytes) else op
        nums = [float(x) for x in operands if isinstance(x, (int, float))]

        # Check if this op is part of the old donut stroke (w=20 and coords in donut)
        is_donut_arc = (
            op_str in ("m", "c", "S") and
            any(406 <= n <= 484 for n in nums) and
            any(348 <= n <= 426 for n in nums)
        )

        # Check if this op is one of the old leader lines
        is_old_leader = False
        if op_str in ("m", "l"):
            if any(abs(n - 409.507) < 0.01 for n in nums) and any(488 <= n <= 520 for n in nums):
                is_old_leader = True
            elif any(abs(n - 429.507) < 0.01 for n in nums) and any(483 <= n <= 520 for n in nums):
                is_old_leader = True
            elif any(abs(n - 449.507) < 0.01 for n in nums) and any(456 <= n <= 520 for n in nums):
                is_old_leader = True
            elif any(abs(n - 342.454) < 0.01 for n in nums) and any(374 <= n <= 425 for n in nums):
                is_old_leader = True

        if is_donut_arc or is_old_leader:
            continue
        new_ops.append((operands, op))

    stream.operations = new_ops
    page[NameObject("/Contents")] = stream


def _draw_donut_chart(c, page_height, values, registered_fonts, template_structure: TemplateStructure):
    """Dynamically render donut slices, dividers, white hole, center total, and leader lines."""
    layout = template_structure.layout_type
    bg = (1.0, 1.0, 1.0) if layout == "modern_manrope" else pdf_mapper.CREAM_BG

    if layout == "classic_neurial":
        cx = 447.6
        cy = page_height - 452.6
        R_outer = 38.0
        R_inner = 24.5
    else:
        cx = 445.0
        cy = page_height - 455.0
        R_outer = 49.0
        R_inner = 29.0

    try:
        govt_amt = float(str(values.get("donut_govt_duty", 0)).replace(",", "").lstrip("₹").strip())
    except (ValueError, TypeError):
        govt_amt = 0.0
    try:
        fppas_amt = float(str(values.get("donut_fppca_charges", 0)).replace(",", "").lstrip("₹").strip())
    except (ValueError, TypeError):
        fppas_amt = 0.0
    try:
        energy_amt = float(str(values.get("donut_energy_charges", 0)).replace(",", "").lstrip("₹").strip())
    except (ValueError, TypeError):
        energy_amt = 0.0
    try:
        fixed_amt = float(str(values.get("donut_fixed_charges", 0)).replace(",", "").lstrip("₹").strip())
    except (ValueError, TypeError):
        fixed_amt = 0.0

    total_amt = govt_amt + fppas_amt + energy_amt + fixed_amt
    if total_amt <= 0:
        total_amt = 1.0

    fixed_deg = (fixed_amt / total_amt) * 360.0
    govt_deg = (govt_amt / total_amt) * 360.0
    fppas_deg = (fppas_amt / total_amt) * 360.0
    energy_deg = (energy_amt / total_amt) * 360.0

    # 4 contiguous slices:
    # Govt ends at 106.0°
    govt_end = 106.0
    govt_start = govt_end - govt_deg
    govt_extent = govt_deg

    fppas_end = govt_start
    fppas_start = fppas_end - fppas_deg
    fppas_extent = fppas_deg

    energy_end = fppas_start
    energy_start = energy_end - energy_deg
    energy_extent = energy_deg

    fixed_start = 106.0
    fixed_extent = fixed_deg

    slices = [
        {"name": "Government duty", "amount": govt_amt, "start": govt_start, "extent": govt_extent, "color": "#9AA0A6", "target": (518.0, 449.507), "side": "right"},
        {"name": "FPPAS charges", "amount": fppas_amt, "start": fppas_start, "extent": fppas_extent, "color": "#5F666D", "target": (518.0, 429.507), "side": "right"},
        {"name": "Energy charges", "amount": energy_amt, "start": energy_start, "extent": energy_extent, "color": "#1F2327", "target": (518.0, 409.507), "side": "right"},
        {"name": "Fixed charges", "amount": fixed_amt, "start": fixed_start, "extent": fixed_extent, "color": "#CCD1D6", "target": (374.0, 342.454), "side": "left"},
    ]

    # Draw wedges
    for s in slices:
        if s["extent"] > 0.001:
            c.setFillColor(HexColor(s["color"]))
            c.wedge(cx - R_outer, cy - R_outer, cx + R_outer, cy + R_outer, s["start"], s["extent"], stroke=0, fill=1)

    # Draw thin dividers (1.2 pt white lines at slice boundaries)
    c.setStrokeColorRGB(*bg)
    c.setLineWidth(1.2)
    for s in slices:
        rad = math.radians(s["start"])
        c.line(cx + (R_inner - 0.5) * math.cos(rad), cy + (R_inner - 0.5) * math.sin(rad),
               cx + (R_outer + 0.5) * math.cos(rad), cy + (R_outer + 0.5) * math.sin(rad))

    # Inner circular mask hole
    c.setFillColorRGB(*bg)
    c.circle(cx, cy, R_inner, stroke=0, fill=1)

    # Center total amount text
    c.setFillColorRGB(0, 0, 0)
    center_font = _resolve_font_name("Manrope-Bold" if layout == "modern_manrope" else "NeurialGrotesk-Bold", registered_fonts)
    clean_total = f"{total_amt:,.2f}"
    rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else center_font
    c.setFont(rupee_font, 9.0)
    c.drawCentredString(cx, cy + 2.5, "₹")
    c.setFont(center_font, 8.5)
    c.drawCentredString(cx, cy - 8.0, clean_total)

    # Leader lines
    if layout == "modern_manrope":
        c.setStrokeColorRGB(0.15, 0.15, 0.15)
        c.setLineWidth(0.75)

        for s in slices:
            tx, ty = s["target"]

            # Calculate start point
            if s["name"] == "Energy charges" and s["extent"] > 90.0:
                # Huge energy slice covers the right side facing ty=409.507 (angle ~27°)
                rad = math.radians(27.34)
            elif s["name"] == "Fixed charges" and s["extent"] > 180.0:
                # Huge fixed slice covers bottom-left facing ty=342.454 (angle ~245.4°)
                rad = math.radians(245.38)
            else:
                mid_deg = (s["start"] + s["extent"] / 2.0) % 360.0
                rad = math.radians(mid_deg)

            sx = cx + R_outer * math.cos(rad)
            sy = cy + R_outer * math.sin(rad)

            if s["side"] == "left":
                # Fixed charges line
                if abs(sy - ty) < 3.0:
                    c.line(sx, ty, tx, ty)
                else:
                    elbow_x = min(sx - 12.0, tx + 10.0)
                    c.line(sx, sy, elbow_x, sy)
                    c.line(elbow_x, sy, elbow_x, ty)
                    c.line(elbow_x, ty, tx, ty)
            else:
                # Right side lines
                if abs(sy - ty) < 3.0:
                    c.line(sx, ty, tx, ty)
                else:
                    elbow_x = min(tx - 15.0, max(sx + 10.0, 485.0))
                    c.line(sx, sy, elbow_x, ty)
                    c.line(elbow_x, ty, tx, ty)


def _build_page_overlay(page_width, page_height, fields, values, registered_fonts, template_structure: TemplateStructure):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))

    # Pass 1: Draw background mask rectangles first
    for field in fields:
        if field.key == "billing_message_box":
            continue
        if field.key == "donut_total_charges":
            continue
        x1 = field.x1 if field.x1 is not None else field.x0 + 150
        rect_x0 = field.x0 - field.pad
        rect_x1 = x1 + field.pad
        rect_y0 = page_height - field.bottom - field.pad
        rect_y1 = page_height - field.top + field.pad
        c.setFillColorRGB(*field.bg)
        c.rect(rect_x0, rect_y0, rect_x1 - rect_x0, rect_y1 - rect_y0, stroke=0, fill=1)

        if field.key == "consumption_sentence_units" and template_structure.layout_type == "classic_neurial":
            extra_bottom = 2.0
            c.setFillColorRGB(*field.bg)
            c.rect(rect_x0, rect_y0 - extra_bottom, rect_x1 - rect_x0,
                   (rect_y1 - rect_y0) + extra_bottom, stroke=0, fill=1)

    # Pass 2: Draw text on top of masked backgrounds
    for field in fields:
        text = values.get(field.key, "")
        if text is None:
            text = ""
        text = str(text)
        if not text:
            continue

        if field.key == "donut_total_charges":
            # Drawn dynamically in _draw_donut_chart
            continue

        if field.key == "headline_due_amount":
            clean_amt = text.lstrip("₹").strip()
            c.setFillColorRGB(0, 0, 0)
            target_font = _resolve_font_name("Manrope-Bold", registered_fonts)
            c.setFont(target_font, 24.0)
            baseline_y = page_height - 353.1
            try:
                c.drawString(33.0, baseline_y, f"₹{clean_amt}")
            except Exception:
                rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else target_font
                c.setFont(rupee_font, 24.0)
                c.drawString(33.0, baseline_y, "₹")
                rw = c.stringWidth("₹", rupee_font, 24.0)
                c.setFont(target_font, 24.0)
                c.drawString(33.0 + rw, baseline_y, clean_amt)
            continue

        if field.key == "previous_payment_line":
            if text:
                c.setFillColorRGB(0, 0, 0)
                norm_font = _resolve_font_name("Manrope-Regular", registered_fonts)
                c.setFont(norm_font, 7.5)
                c.drawString(250.0, page_height - 304.5, text)
                c.drawString(250.0, page_height - 315.5, "Payment received through Billdesk - NetBanking.")
            continue

        if field.key in ("coupon_group_no", "coupon_customer_id", "coupon_due_date", "coupon_amount_upto_due"):
            c.setFillColorRGB(0, 0, 0)
            coupon_font = _resolve_font_name("Manrope-Medium", registered_fonts)
            c.setFont(coupon_font, 6.0)
            coupon_baseline = page_height - 820.0
            if field.key == "coupon_group_no":
                c.drawString(96.0, coupon_baseline, text or "DI070010")
            elif field.key == "coupon_customer_id":
                c.drawString(250.0, coupon_baseline, text)
            elif field.key == "coupon_due_date":
                c.drawString(377.0, coupon_baseline, text)
            elif field.key == "coupon_amount_upto_due":
                clean_amt = text.lstrip("₹").strip()
                amt_str = f"₹{clean_amt}"
                try:
                    c.drawString(526.0, coupon_baseline, amt_str)
                except Exception:
                    rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else coupon_font
                    c.setFont(rupee_font, 6.0)
                    c.drawString(526.0, coupon_baseline, "₹")
                    rw = c.stringWidth("₹", rupee_font, 6.0)
                    c.setFont(coupon_font, 6.0)
                    c.drawString(526.0 + rw, coupon_baseline, clean_amt)
            continue

        x1 = field.x1 if field.x1 is not None else field.x0 + 150

        c.setFillColorRGB(0, 0, 0)
        resolved_font = _resolve_font_name(field.font, registered_fonts)
        font_size = field.size
        max_width = max(x1 - field.x0, 20.0)
        while font_size > 5.0 and c.stringWidth(text, resolved_font, font_size) > max_width:
            font_size -= 0.5
        c.setFont(resolved_font, font_size)
        baseline_y = page_height - field.bottom

        is_bold_field = "Bold" in field.font or "Extrabold" in field.font
        has_rupee = text.startswith("₹")

        if field.align == "right":
            if has_rupee:
                clean_amt = text.lstrip("₹").strip()
                formatted_amt = f"₹{clean_amt}"
                try:
                    c.setFont(resolved_font, font_size)
                    c.drawRightString(x1, baseline_y, formatted_amt)
                except Exception:
                    rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else resolved_font
                    rw = c.stringWidth("₹", rupee_font, font_size)
                    aw = c.stringWidth(clean_amt, resolved_font, font_size)
                    total_w = rw + aw
                    c.setFont(rupee_font, font_size)
                    c.drawString(x1 - total_w, baseline_y, "₹")
                    c.setFont(resolved_font, font_size)
                    c.drawString(x1 - total_w + rw, baseline_y, clean_amt)
            else:
                c.drawRightString(x1, baseline_y, text)
        elif field.align == "center":
            if has_rupee:
                clean_amt = text.lstrip("₹").strip()
                formatted_amt = f"₹{clean_amt}"
                try:
                    c.setFont(resolved_font, font_size)
                    c.drawCentredString((field.x0 + x1) / 2, baseline_y, formatted_amt)
                except Exception:
                    rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else resolved_font
                    rw = c.stringWidth("₹", rupee_font, font_size)
                    aw = c.stringWidth(clean_amt, resolved_font, font_size)
                    total_w = rw + aw
                    start_x = (field.x0 + x1) / 2 - total_w / 2
                    c.setFont(rupee_font, font_size)
                    c.drawString(start_x, baseline_y, "₹")
                    c.setFont(resolved_font, font_size)
                    c.drawString(start_x + rw, baseline_y, clean_amt)
            else:
                c.drawCentredString((field.x0 + x1) / 2, baseline_y, text)
        else:
            if has_rupee:
                clean_amt = text.lstrip("₹").strip()
                formatted_amt = f"₹{clean_amt}"
                try:
                    c.setFont(resolved_font, font_size)
                    c.drawString(field.x0, baseline_y, formatted_amt)
                except Exception:
                    rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else resolved_font
                    c.setFont(rupee_font, font_size)
                    c.drawString(field.x0, baseline_y, "₹")
                    rupee_width = c.stringWidth("₹", rupee_font, font_size)
                    c.setFont(resolved_font, font_size)
                    c.drawString(field.x0 + rupee_width, baseline_y, clean_amt)
            else:
                c.drawString(field.x0, baseline_y, text)

    # Ensure left bank line of QR code box is 100% complete and fulfilled without overlapping WhatsApp icon
    if template_structure.layout_type == "modern_manrope" and any(f.key == "area" for f in fields):
        c.setStrokeColorRGB(0.161, 0.149, 0.38)
        c.setLineWidth(1.2)
        c.line(357.0, page_height - 92.0, 357.0, page_height - 22.0)

    # Template-specific artwork segments: redraw meter box bottom-right cut
    if any(f.key == "meter_no" for f in fields):
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.7)
        c.line(109.5, page_height - 503.0, 119.0, page_height - 493.5)

    # Dynamic Donut Chart & Leader Lines rendering (Page 0)
    if any(f.key == "donut_total_charges" for f in fields):
        _draw_donut_chart(c, page_height, values, registered_fonts, template_structure)

    if template_structure.layout_type == "classic_neurial":

        if any(f.key == "donut_total_charges" for f in fields):
            sx0, stop, sx1, sbottom = (41.0, 530.0, 300.0, 684.0)
            c.setFillColorRGB(*pdf_mapper.CREAM_BG)
            c.rect(sx0, page_height - sbottom, sx1 - sx0, sbottom - stop, stroke=0, fill=1)
            ad_path = "static/images/rccb_ad1.png"
            if os.path.exists(ad_path):
                from reportlab.lib.utils import ImageReader
                ad_image = ImageReader(ad_path)
                c.drawImage(ad_image, sx0, page_height - sbottom, sx1 - sx0, sbottom - stop,
                            preserveAspectRatio=True, anchor='n', mask='auto')

            # Leader line
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.3)
            c.line(370.02, page_height - 435.07, 387.28, page_height - 435.07)

    # Consumption Bar Chart (if template has chart)
    if template_structure.has_chart and template_structure.chart_info and any(f.key.startswith("chart_") or f.key == "consumption_units" for f in fields):
        chart = template_structure.chart_info
        axis_y = chart.get("axis_y", 680.0)
        clear_top = chart.get("clear_top", 580.0)
        clear_x0 = chart.get("clear_x0", 315.0)
        clear_x1 = chart.get("clear_x1", 545.0)
        bar_x_positions = chart.get("bar_x_positions", [])
        chart_font = chart.get("font", "Manrope-Regular")

        # Clear old static chart data before drawing the dynamic chart
        chart_bg = (1.0, 1.0, 1.0) if template_structure.layout_type == "modern_manrope" else pdf_mapper.CREAM_BG
        c.setFillColorRGB(*chart_bg)
        # Erase bar area
        c.rect(clear_x0 - 2.0, page_height - axis_y, clear_x1 - clear_x0 + 4.0, axis_y - clear_top, stroke=0, fill=1)
        # Erase axis labels area
        c.rect(clear_x0 - 2.0, page_height - (axis_y + 22.0), clear_x1 - clear_x0 + 4.0, 22.0, stroke=0, fill=1)

        chart_values = values.get("chart_values", [])
        month_font = _resolve_font_name("Manrope-Bold", registered_fonts)
        year_font = _resolve_font_name("Manrope-Regular", registered_fonts)

        for pair_idx in range(6):
            m_label = values.get(f"chart_month_{pair_idx}", "")
            y_prev = str(values.get(f"chart_year_{pair_idx * 2}", "") or "")
            y_curr = str(values.get(f"chart_year_{pair_idx * 2 + 1}", "") or "")

            left_x0, left_x1 = bar_x_positions[pair_idx * 2]
            right_x0, right_x1 = bar_x_positions[pair_idx * 2 + 1]
            left_center = (left_x0 + left_x1) / 2.0
            right_center = (right_x0 + right_x1) / 2.0
            pair_center = (left_x0 + right_x1) / 2.0

            # Year shown for each bar (below the baseline)
            c.setFont(year_font, 5.5)
            c.setFillColorRGB(0.0, 0.0, 0.0)
            if y_prev:
                c.drawCentredString(left_center, page_height - 686.4, y_prev)
            if y_curr:
                c.drawCentredString(right_center, page_height - 686.4, y_curr)

            # Month centered below the pair
            if m_label:
                c.setFont(month_font, 6.0)
                c.setFillColorRGB(0.0, 0.0, 0.0)
                c.drawCentredString(pair_center, page_height - 695.5, m_label)

        PRIOR_YEAR_COLOR = (0.827, 0.827, 0.827)
        CURRENT_YEAR_COLOR = (0.55, 0.55, 0.55)
        HIGHLIGHT_COLOR = (0.15, 0.15, 0.15)
        max_chart_height = axis_y - clear_top
        _valid_vals = [float(v) for v in chart_values if v is not None]
        _tallest = max(_valid_vals) if _valid_vals else 0
        target_fill_ratio = 0.65
        chart_pt_per_unit = ((max_chart_height * target_fill_ratio / _tallest) if _tallest > 0 else 0.2)

        resolved_chart_font = _resolve_font_name("Manrope-Regular", registered_fonts)
        hl_idx = values.get("highlight_bar_index")

        for i, raw_value in enumerate(chart_values):
            if raw_value is None or i >= len(bar_x_positions):
                continue
            try:
                value_num = float(raw_value)
            except (TypeError, ValueError):
                continue

            bar_x0, bar_x1 = bar_x_positions[i]
            bar_height = min(value_num * chart_pt_per_unit, axis_y - clear_top)

            if hl_idx is not None and i == hl_idx:
                bar_color = HIGHLIGHT_COLOR
            elif hl_idx is None and i == len(bar_x_positions) - 1:
                bar_color = HIGHLIGHT_COLOR
            elif i % 2 == 0:
                bar_color = PRIOR_YEAR_COLOR
            else:
                bar_color = CURRENT_YEAR_COLOR

            c.setFillColorRGB(*bar_color)
            c.rect(bar_x0, page_height - axis_y, bar_x1 - bar_x0, bar_height, stroke=0, fill=1)

            bar_top_from_axis = axis_y - bar_height
            label_bottom_topcoord = bar_top_from_axis - 4.0
            c.setFillColorRGB(0, 0, 0)
            c.setFont(resolved_chart_font, 5)
            c.drawCentredString((bar_x0 + bar_x1) / 2, page_height - label_bottom_topcoord, str(int(value_num)))

        # Draw the horizontal baseline axis line AFTER bars so it is solid, continuous and crisp across all bars
        if template_structure.layout_type == "modern_manrope":
            c.setStrokeColorRGB(0.4, 0.4, 0.4)
            c.setLineWidth(1.0)
            c.line(318.0, page_height - 678.75, 543.0, page_height - 678.75)
        else:
            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.setLineWidth(0.5)
            c.line(clear_x0, page_height - axis_y, clear_x1, page_height - axis_y)

    # Billing Message Box: classic_neurial uses dynamic prompt rebate box; modern_manrope keeps master template message
    if any(f.key == "billing_message_box" for f in fields):
        if template_structure.layout_type == "classic_neurial":
            box_field = next(f for f in fields if f.key == "billing_message_box")
            draw_billing_message(
                c, page_height,
                box=(box_field.x0, box_field.top, box_field.x1, box_field.bottom),
                registered_fonts=registered_fonts,
                font_name=_resolve_font_name("NeurialGrotesk-Regular", registered_fonts),
                bold_font_name=_resolve_font_name("NeurialGrotesk-Bold", registered_fonts),
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


def validate_bill_generation_data(values: dict, bill, consumer: dict, consumption_history: dict = None):
    """
    Automated check suite run before saving the PDF (Requirement 12: Checks A through J).
    """
    # Check A: Final bill amount is valid
    if bill.total_amount_due is None or not isinstance(bill.total_amount_due, (int, float)):
        raise ValueError("[CHECK A FAILED] Final bill amount is not a valid numeric value.")

    # Check B: All component values are numeric
    for name, val in [("fixed_charges", bill.fixed_charges), ("energy_charges", bill.energy_charges),
                      ("fppca_charges", bill.fppca_charges), ("govt_duty", bill.govt_duty)]:
        if val is None or not isinstance(val, (int, float)):
            raise ValueError(f"[CHECK B FAILED] Component {name} is not numeric: {val}")

    # Check C: Donut component sum is correct
    donut_total = float(values.get("donut_total_amount") or 0)
    sum_components = round(bill.fixed_charges + bill.energy_charges + bill.fppca_charges + bill.govt_duty, 2)
    if abs(donut_total - sum_components) > 0.02:
        raise ValueError(f"[CHECK C FAILED] Donut total {donut_total} != sum of components {sum_components}")

    # Check D: Donut center equals donut component total
    donut_center_str = str(values.get("donut_total_charges", "")).replace(",", "").lstrip("₹").strip()
    try:
        donut_center_val = float(donut_center_str)
    except ValueError:
        raise ValueError(f"[CHECK D FAILED] Donut center value '{donut_center_str}' cannot be parsed as float.")
    if abs(donut_center_val - sum_components) > 0.02:
        raise ValueError(f"[CHECK D FAILED] Donut center {donut_center_val} != component total {sum_components}")

    # Check E: Every donut slice percentage is calculated from its actual amount
    slices = values.get("donut_chart_data") or []
    if sum_components > 0:
        for s in slices:
            amt = float(s.get("amount", 0))
            expected_pct = (amt / sum_components) * 100.0
            if abs(s.get("percentage", 0) - expected_pct) > 0.05:
                raise ValueError(f"[CHECK E FAILED] Slice {s.get('label')} percentage {s.get('percentage')} != expected {expected_pct}")
            expected_ang = (amt / sum_components) * 360.0
            if abs(s.get("angle", 0) - expected_ang) > 0.05:
                raise ValueError(f"[CHECK E FAILED] Slice {s.get('label')} angle {s.get('angle')} != expected {expected_ang}")

    # Check F: Consumption values match source data
    if str(int(bill.units_consumed)) != values.get("consumption_units"):
        raise ValueError(f"[CHECK F FAILED] Consumption units {values.get('consumption_units')} != bill units {bill.units_consumed}")
    chart_vals = values.get("chart_values", [])
    if chart_vals:
        hl_idx = values.get("highlight_bar_index")
        if hl_idx is not None and hl_idx < len(chart_vals):
            check_val = chart_vals[hl_idx]
            if check_val is not None and check_val != bill.units_consumed:
                raise ValueError(f"[CHECK F FAILED] Active chart value {check_val} != bill units {bill.units_consumed}")
        else:
            non_empty_vals = [v for v in chart_vals if v is not None]
            if non_empty_vals and non_empty_vals[-1] != bill.units_consumed:
                raise ValueError(f"[CHECK F FAILED] Final chart value {non_empty_vals[-1]} != bill units {bill.units_consumed}")

    # Check G: Month labels match their corresponding consumption values
    m_label = values.get("billing_month")
    if not m_label:
        raise ValueError("[CHECK G FAILED] Billing month label is empty.")

    # Check H: No hardcoded/demo chart values remain
    if round(bill.total_amount_due, 2) != 577.84 and abs(donut_center_val - 577.84) < 0.01:
        raise ValueError("[CHECK H FAILED] Donut center still contains hardcoded demo value 577.84")

    # Check I: No stale cached data is used
    if values.get("customer_id") != str(consumer.get("customer_id") or ""):
        raise ValueError("[CHECK I FAILED] Mapped customer_id does not match consumer input")

    # Check J: PDF headline amount matches rounded bill total
    headline_clean = float(str(values.get("headline_due_amount", "")).replace(",", "").lstrip("₹").strip())
    if abs(headline_clean - round(bill.total_amount_due)) > 0.02:
        raise ValueError(f"[CHECK J FAILED] Headline amount {headline_clean} != rounded bill total {round(bill.total_amount_due)}")

    print(f"[PRE-FLIGHT VALIDATION] Successfully verified checks A-J for Customer {consumer.get('customer_id')}")


def generate_bill_pdf(template_path: str, consumer: dict, bill, output_path: str,
                      consumption_history: dict = None, template_structure: Optional[TemplateStructure] = None) -> str:
    """
    Generates a single filled PDF invoice for one consumer record using the specified template PDF.
    """
    if template_structure is None:
        template_structure = detect_template_structure(template_path)

    values = pdf_mapper.build_field_values(consumer, bill, consumption_history=consumption_history, template_info=template_structure)

    # Automated check suite before rendering & saving (Requirement 12)
    validate_bill_generation_data(values, bill, consumer, consumption_history)

    reader = PdfReader(template_path)
    registered_fonts = font_manager.ensure_template_fonts_registered(template_path)
    writer = PdfWriter()

    fields_by_page = template_structure.fields_by_page

    for page_index, page in enumerate(reader.pages):
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        if page_index == 0 and template_structure.layout_type == "modern_manrope":
            _strip_template_donut_and_leaders(page, reader)

        page_fields = fields_by_page.get(page_index, [])
        if page_fields:
            overlay_page = _build_page_overlay(
                page_width, page_height, page_fields, values, registered_fonts, template_structure
            )
            page.merge_page(overlay_page)

        writer.add_page(page)

    output_dir = os.path.dirname(output_path) or "."
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path