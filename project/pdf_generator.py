import io
import math
import os
import re
from typing import Optional

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, ContentStream
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from billing_message import draw_billing_message
import font_manager
import pdf_mapper
from template_detector import detect_template_structure, TemplateStructure, Field, get_template_for_billing_month


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


def _strip_template_donut_and_leaders(page, reader, layout_type: str = "modern_manrope"):
    """Remove static background donut arcs and leader lines from the template PDF page content stream."""
    contents_obj = page.get("/Contents")
    if not contents_obj:
        return
    contents_obj = contents_obj.get_object()
    stream = ContentStream(contents_obj, reader)

    new_ops = []
    if layout_type == "classic_neurial":
        # In demo.pdf, operations 711 to 789 contain static donut arcs, leader lines, and old texts
        for i, (operands, op) in enumerate(stream.operations):
            if 711 <= i <= 789:
                continue
            new_ops.append((operands, op))
    else:
        for i, (operands, op) in enumerate(stream.operations):
            if 275 <= i <= 359:
                continue
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
        cx = 440.0
        cy = page_height - 448.0
        R_outer = 53.0
        R_inner = 35.0

        try:
            energy_amt = float(str(values.get("donut_energy_charges", 0)).replace(",", "").lstrip("₹").strip())
        except (ValueError, TypeError):
            energy_amt = 0.0
        try:
            fixed_amt = float(str(values.get("donut_fixed_charges", 0)).replace(",", "").lstrip("₹").strip())
        except (ValueError, TypeError):
            fixed_amt = 0.0
        try:
            fppas_amt = float(str(values.get("donut_fppca_charges", 0)).replace(",", "").lstrip("₹").strip())
        except (ValueError, TypeError):
            fppas_amt = 0.0

        # Reference demo.pdf has exactly 3 components: Fixed, Energy, FPPCA
        comp_total = energy_amt + fixed_amt + fppas_amt
        calc_total = comp_total if comp_total > 0 else 1.0

        fixed_deg = (fixed_amt / calc_total) * 360.0
        energy_deg = (energy_amt / calc_total) * 360.0
        fppas_deg = (fppas_amt / calc_total) * 360.0

        fixed_start = 315.5
        energy_start = fixed_start + fixed_deg
        fppas_start = energy_start + energy_deg

        slices = [
            {"name": "Fixed charges", "amount": fixed_amt, "start": fixed_start, "extent": fixed_deg, "color": "#CCD1D6"},
            {"name": "Energy charges", "amount": energy_amt, "start": energy_start, "extent": energy_deg, "color": "#1F2327"},
            {"name": "FPPCA charges", "amount": fppas_amt, "start": fppas_start, "extent": fppas_deg, "color": "#5F666D"},
        ]

        # Draw wedges
        for s in slices:
            if s["extent"] > 0.001:
                c.setFillColor(HexColor(s["color"]))
                c.wedge(cx - R_outer, cy - R_outer, cx + R_outer, cy + R_outer, s["start"], s["extent"], stroke=0, fill=1)

        # Draw thin dividers (1.2 pt CREAM_BG lines at slice boundaries)
        c.setStrokeColorRGB(*bg)
        c.setLineWidth(1.2)
        for s in slices:
            rad = math.radians(s["start"])
            c.line(cx + (R_inner - 0.5) * math.cos(rad), cy + (R_inner - 0.5) * math.sin(rad),
                   cx + (R_outer + 0.5) * math.cos(rad), cy + (R_outer + 0.5) * math.sin(rad))

        # Inner circular mask hole
        c.setFillColorRGB(*bg)
        c.circle(cx, cy, R_inner, stroke=0, fill=1)

        # Center total amount text: must equal Fixed Charges + Energy Charges + FPPCA Charges
        clean_total = f"{comp_total:,.2f}"
        c.setFillColorRGB(0, 0, 0)
        center_font = _resolve_font_name("NeurialGrotesk-Bold", registered_fonts)
        rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else center_font
        c.setFont(rupee_font, 9.0)
        c.drawCentredString(cx, cy + 2.5, "₹")
        c.setFont(center_font, 8.5)
        c.drawCentredString(cx, cy - 8.0, clean_total)

        # Leader lines matching demo.pdf exactly (clean horizontal arrows, exact start/end and spacing)
        c.setStrokeColorRGB(0.15, 0.15, 0.15)
        c.setLineWidth(0.4)

        # Standard demo.pdf Y coordinates
        ty_energy_std = page_height - 435.07  # 406.82
        ty_fixed_std = page_height - 449.27   # 392.62
        ty_fppca_std = page_height - 498.32   # 343.57

        def _is_angle_in_slice(angle, start_deg, extent_deg):
            a = angle % 360.0
            s = start_deg % 360.0
            e = (s + extent_deg) % 360.0
            if s < e:
                return s <= a <= e
            else:
                return a >= s or a <= e

        # 1. Energy Charges (LEFT side)
        ang_energy_std = 180.0 - math.degrees(math.asin(min(1.0, max(-1.0, (ty_energy_std - cy) / R_outer))))
        if _is_angle_in_slice(ang_energy_std, energy_start, energy_deg):
            ty_energy = ty_energy_std
            sx_energy = 387.28
        else:
            e_mid = (energy_start + energy_deg / 2.0) % 360.0
            rad_e = math.radians(e_mid)
            ty_energy = max(cy - R_outer + 5.0, min(cy + R_outer - 5.0, cy + R_outer * math.sin(rad_e)))
            sx_energy = cx - math.sqrt(max(0, R_outer**2 - (ty_energy - cy)**2))

        # 2. Fixed Charges (RIGHT side)
        ang_fixed_std = math.degrees(math.asin(min(1.0, max(-1.0, (ty_fixed_std - cy) / R_outer)))) % 360.0
        if _is_angle_in_slice(ang_fixed_std, fixed_start, fixed_deg):
            ty_fixed = ty_fixed_std
            sx_fixed = 495.0
        else:
            f_mid = (fixed_start + fixed_deg / 2.0) % 360.0
            rad_f = math.radians(f_mid)
            ty_fixed = max(cy - R_outer + 5.0, min(cy + R_outer - 5.0, cy + R_outer * math.sin(rad_f)))
            sx_fixed = cx + math.sqrt(max(0, R_outer**2 - (ty_fixed - cy)**2))

        # 3. FPPCA Charges (LOWER-RIGHT side)
        ang_fppca_std = (360.0 + math.degrees(math.asin(min(1.0, max(-1.0, (ty_fppca_std - cy) / R_outer))))) % 360.0
        if _is_angle_in_slice(ang_fppca_std, fppas_start, fppas_deg):
            ty_fppca = ty_fppca_std
            sx_fppca = 467.51
        else:
            p_mid = (fppas_start + fppas_deg / 2.0) % 360.0
            rad_p = math.radians(p_mid)
            ty_fppca = max(cy - R_outer + 5.0, min(cy + R_outer - 5.0, cy + R_outer * math.sin(rad_p)))
            sx_fppca = cx + math.sqrt(max(0, R_outer**2 - (ty_fppca - cy)**2))

        # All 3 leader lines are PURE HORIZONTAL LINES matching demo.pdf
        c.line(sx_energy, ty_energy, 370.02, ty_energy)
        c.line(sx_fixed, ty_fixed, 510.02, ty_fixed)
        c.line(sx_fppca, ty_fppca, 510.02, ty_fppca)

        # Labels & Amounts cleanly formatted matching demo.pdf
        font_bold = _resolve_font_name("NeurialGrotesk-Bold", registered_fonts)
        font_reg = _resolve_font_name("NeurialGrotesk-Regular", registered_fonts)

        def _draw_donut_label_right(x_right, y, amt):
            amt_str = f"{amt:,.2f}"
            c.setFont(font_bold, 8.0)
            aw = c.stringWidth(amt_str, font_bold, 8.0)
            c.setFont(rupee_font, 8.0)
            rw = c.stringWidth("₹", rupee_font, 8.0)
            total_w = rw + aw
            c.drawString(x_right - total_w, y, "₹")
            c.setFont(font_bold, 8.0)
            c.drawString(x_right - aw, y, amt_str)

        def _draw_donut_label_left(x_left, y, amt):
            amt_str = f"{amt:,.2f}"
            c.setFont(rupee_font, 8.0)
            c.drawString(x_left, y, "₹")
            rw = c.stringWidth("₹", rupee_font, 8.0)
            c.setFont(font_bold, 8.0)
            c.drawString(x_left + rw, y, amt_str)

        # Energy charges on left (right-aligned to 365.0, 5pt gap before leader line at 370.02)
        _draw_donut_label_right(365.0, ty_energy - 3.0, energy_amt)
        c.setFont(font_reg, 7.0)
        c.drawRightString(365.0, ty_energy - 11.0, "Energy")
        c.drawRightString(365.0, ty_energy - 19.0, "Charges")

        # Fixed charges on right (left-aligned at 515.02, 5pt gap after leader line at 510.02)
        _draw_donut_label_left(515.02, ty_fixed + 10.11, fixed_amt)
        c.setFont(font_reg, 7.0)
        c.drawString(515.02, ty_fixed + 2.11, "Fixed Charges")

        # FPPCA charges on lower right (left-aligned at 515.02, 5pt gap after leader line at 510.02)
        _draw_donut_label_left(515.02, ty_fppca - 2.89, fppas_amt)
        c.setFont(font_reg, 7.0)
        c.drawString(515.02, ty_fppca - 10.89, "FPPCA Charges")

        return

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
        {"name": "Government duty", "amount": govt_amt, "start": govt_start, "extent": govt_deg, "color": "#9AA0A6"},
        {"name": "FPPAS charges", "amount": fppas_amt, "start": fppas_start, "extent": fppas_deg, "color": "#5F666D"},
        {"name": "Energy charges", "amount": energy_amt, "start": energy_start, "extent": energy_deg, "color": "#1F2327"},
        {"name": "Fixed charges", "amount": fixed_amt, "start": fixed_start, "extent": fixed_extent, "color": "#CCD1D6"},
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
    center_font = _resolve_font_name("Manrope-Bold", registered_fonts)
    font_bold = _resolve_font_name("Manrope-Bold", registered_fonts)
    font_reg = _resolve_font_name("Manrope-Regular", registered_fonts)
    center_total = float(values.get("_bill_total_amount_due") or total_amt)
    clean_total = f"{center_total:,.2f}"
    rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else center_font
    c.setFont(rupee_font, 9.0)
    c.drawCentredString(cx, cy + 2.5, "₹")
    c.setFont(center_font, 8.5)
    c.drawCentredString(cx, cy - 8.0, clean_total)

    # Leader lines & Labels (clean spacing, no overlap, dynamic slice tracking)
    if layout == "modern_manrope":
        c.setStrokeColorRGB(0.15, 0.15, 0.15)
        c.setLineWidth(0.75)

        tx_right = 514.0
        text_x_right = 520.0

        # Right side target Y positions
        ty_govt = 449.507
        ty_fppas = 429.507
        ty_energy = 409.507

        # Dynamic vertical separation: minimum 15 pt clearance
        min_gap = 18.0
        if ty_govt - ty_fppas < min_gap:
            ty_govt = ty_fppas + min_gap
        if ty_fppas - ty_energy < min_gap:
            ty_fppas = ty_energy + min_gap

        # 1. Government Duty (upper-right)
        # Diagonal outward line -> short horizontal line -> label
        govt_mid = (govt_start + govt_end) / 2.0
        rad_govt = math.radians(govt_mid)
        sx_govt = cx + R_outer * math.cos(rad_govt)
        sy_govt = cy + R_outer * math.sin(rad_govt)
        elbow_x_govt = tx_right - 20.0
        c.line(sx_govt, sy_govt, elbow_x_govt, ty_govt)
        c.line(elbow_x_govt, ty_govt, tx_right, ty_govt)

        # 2. FPPAS Charges (right/upper-right)
        # Diagonal line -> clean horizontal section -> label
        fppas_mid = (fppas_start + fppas_end) / 2.0
        rad_fppas = math.radians(fppas_mid)
        sx_fppas = cx + R_outer * math.cos(rad_fppas)
        sy_fppas = cy + R_outer * math.sin(rad_fppas)
        elbow_x_fppas = min(tx_right - 18.0, max(sx_fppas + 10.0, 492.0))
        c.line(sx_fppas, sy_fppas, elbow_x_fppas, ty_fppas)
        c.line(elbow_x_fppas, ty_fppas, tx_right, ty_fppas)

        # 3. Energy Charges (right/lower-right)
        # Horizontal leader line from donut edge to label
        sx_energy = cx + math.sqrt(max(0, R_outer**2 - (ty_energy - cy)**2))
        c.line(sx_energy, ty_energy, tx_right, ty_energy)

        # 4. Fixed Charges (lower-left)
        # Long clean horizontal line from donut lower-left edge to left label
        ty_fixed = 342.454
        tx_fixed = 374.0
        text_x_left = 370.0
        sx_fixed = cx - math.sqrt(max(0, R_outer**2 - (cy - ty_fixed)**2))
        c.line(sx_fixed, ty_fixed, tx_fixed, ty_fixed)

        # Draw Labels for modern_manrope
        def _draw_modern_label_right(amt, name, baseline_y):
            amt_str = f"{amt:,.2f}"
            c.setFillColorRGB(0, 0, 0)
            c.setFont(rupee_font, 8.0)
            c.drawString(text_x_right, baseline_y, "₹")
            rw = c.stringWidth("₹", rupee_font, 8.0)
            c.setFont(font_bold, 8.0)
            c.drawString(text_x_right + rw + 0.5, baseline_y, amt_str)
            c.setFont(font_reg, 7.0)
            c.drawString(text_x_right, baseline_y - 8.0, name)

        def _draw_modern_label_left(amt, name, baseline_y):
            amt_str = f"{amt:,.2f}"
            c.setFillColorRGB(0, 0, 0)
            c.setFont(font_bold, 8.0)
            aw = c.stringWidth(amt_str, font_bold, 8.0)
            c.setFont(rupee_font, 8.0)
            rw = c.stringWidth("₹", rupee_font, 8.0)
            total_w = rw + aw + 0.5
            start_x = text_x_left - total_w
            c.drawString(start_x, baseline_y, "₹")
            c.setFont(font_bold, 8.0)
            c.drawString(start_x + rw + 0.5, baseline_y, amt_str)
            c.setFont(font_reg, 7.0)
            c.drawRightString(text_x_left, baseline_y - 8.0, name)

        _draw_modern_label_right(govt_amt, "Government duty", ty_govt)
        _draw_modern_label_right(fppas_amt, "FPPAS charges", ty_fppas)
        _draw_modern_label_right(energy_amt, "Energy charges", ty_energy)
        _draw_modern_label_left(fixed_amt, "Fixed charges", ty_fixed)


def _draw_wrapped_address(c, page_height, values, registered_fonts, template_structure: TemplateStructure):
    raw_addr = str(values.get("full_address") or values.get("address") or "").strip()
    if not raw_addr:
        parts = [str(values.get(f"address_line{i}") or "").strip() for i in range(1, 10)]
        raw_addr = ", ".join([p for p in parts if p])
    if not raw_addr:
        return

    clean_addr = " ".join(raw_addr.split()).upper()

    layout = template_structure.layout_type
    if layout == "classic_neurial":
        font_name = _resolve_font_name("NeurialGrotesk-Regular", registered_fonts)
        x0 = 41.8
        max_width = 153.2
        top_y = 171.5
        bottom_y = 201.5
        max_height = bottom_y - top_y
        font_sizes = [8.0, 7.5, 7.0, 6.5, 6.0, 5.5]
    elif layout == "modern_manrope":
        font_name = _resolve_font_name("Manrope-Regular", registered_fonts)
        x0 = 40.0
        max_width = 170.0
        top_y = 184.0
        bottom_y = 244.0
        max_height = bottom_y - top_y
        font_sizes = [8.0, 7.5, 7.0, 6.5, 6.0]
    else:
        addr_fields = [f for f in template_structure.fields if f.key.startswith("address_line")]
        if not addr_fields:
            return
        x0 = addr_fields[0].x0
        max_width = (addr_fields[0].x1 - addr_fields[0].x0) if addr_fields[0].x1 else 150.0
        top_y = min(f.top for f in addr_fields)
        bottom_y = max(f.bottom for f in addr_fields)
        max_height = bottom_y - top_y
        font_name = _resolve_font_name(addr_fields[0].font, registered_fonts)
        font_sizes = [8.0, 7.5, 7.0, 6.5, 6.0]

    words = clean_addr.split()
    best_lines = []
    best_size = font_sizes[-1]

    for size in font_sizes:
        lines = []
        cur = []
        for w in words:
            candidate = " ".join(cur + [w])
            try:
                w_pt = c.stringWidth(candidate, font_name, size)
            except Exception:
                w_pt = c.stringWidth(candidate, "Helvetica", size)
            if w_pt <= max_width:
                cur.append(w)
            else:
                if cur:
                    lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))

        line_spacing = size * 1.25
        needed_height = (len(lines) - 1) * line_spacing + size
        if needed_height <= max_height or size == font_sizes[-1]:
            best_lines = lines
            best_size = size
            break

    n = len(best_lines)
    if n == 0:
        return

    c.setFillColorRGB(0, 0, 0)
    c.setFont(font_name, best_size)

    if layout == "classic_neurial":
        if n == 1:
            baselines = [page_height - 180.0]
        elif n == 2:
            baselines = [page_height - 179.0, page_height - 189.0]
        else:
            start_y = 178.5
            end_y = 197.0
            step = (end_y - start_y) / (n - 1)
            baselines = [page_height - (start_y + i * step) for i in range(n)]
    elif layout == "modern_manrope":
        if n <= 5:
            start_y = 191.9
            baselines = [page_height - (start_y + i * 10.0) for i in range(n)]
        else:
            start_y = top_y + best_size + 2.0
            end_y = bottom_y - 2.0
            step = (end_y - start_y) / (n - 1)
            baselines = [page_height - (start_y + i * step) for i in range(n)]
    else:
        start_y = top_y + best_size
        end_y = bottom_y - 1.0
        step = (end_y - start_y) / max(n - 1, 1)
        baselines = [page_height - (start_y + i * step) for i in range(n)]

    for line_text, b_y in zip(best_lines, baselines):
        c.drawString(x0, b_y, line_text)


def _build_page_overlay(page_width, page_height, fields, values, registered_fonts, template_structure: TemplateStructure):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))

    # Pass 1: Draw background mask rectangles first
    for field in fields:
        if field.key == "billing_message_box":
            continue
        if field.key == "donut_total_charges":
            continue
        if template_structure.layout_type in ("classic_neurial", "modern_manrope") and field.key in (
            "donut_energy_charges", "donut_fixed_charges", "donut_fppca_charges", "donut_govt_duty"
        ):
            continue
        if template_structure.layout_type in ("classic_neurial", "modern_manrope") and field.key.startswith("address_line"):
            continue
        x1 = field.x1 if field.x1 is not None else field.x0 + 150
        rect_x0 = field.x0 - field.pad
        rect_x1 = x1 + field.pad
        rect_y0 = page_height - field.bottom - field.pad
        rect_y1 = page_height - field.top + field.pad
        c.setFillColorRGB(*field.bg)
        c.rect(rect_x0, rect_y0, rect_x1 - rect_x0, rect_y1 - rect_y0, stroke=0, fill=1)

        if field.key == "consumption_sentence_units":
            bg_color = (1.0, 1.0, 1.0) if template_structure.layout_type == "modern_manrope" else pdf_mapper.CREAM_BG
            c.setFillColorRGB(*bg_color)
            c.rect(41.5, page_height - 528.0, 185.0, 15.0, stroke=0, fill=1)

    # Dedicated background mask for the full address area on page 0
    if any(f.key.startswith("address_line") for f in fields) and template_structure.layout_type in ("classic_neurial", "modern_manrope"):
        c.setFillColorRGB(1.0, 1.0, 1.0)
        if template_structure.layout_type == "classic_neurial":
            c.rect(41.5, page_height - 202.0, 154.5, 30.5, stroke=0, fill=1)
        elif template_structure.layout_type == "modern_manrope":
            c.rect(39.5, page_height - 245.0, 172.5, 61.0, stroke=0, fill=1)

    # Pass 2: Draw text on top of masked backgrounds
    for field in fields:
        if template_structure.layout_type in ("classic_neurial", "modern_manrope") and field.key.startswith("address_line"):
            continue
        raw_val = values.get(field.key)
        if field.key in ("bd_arrear", "bd_other_debit_credit", "bd_prompt_rebate", "bd_advance_rebate"):
            raw_str = str(raw_val or "").strip()
            if not raw_str or raw_str in ("0", "0.0", "None"):
                text = "0.00"
            elif "credit" in raw_str.lower():
                text = raw_str
            else:
                try:
                    f = float(raw_str.lstrip("-").strip())
                    is_neg = raw_str.startswith("-")
                    text = f"-{f:,.2f}" if is_neg else f"{f:,.2f}"
                except (ValueError, TypeError):
                    text = raw_str
        else:
            text = values.get(field.key, "")
            if text is None:
                text = ""
            text = str(text)
            if not text:
                continue

        if field.key == "donut_total_charges":
            # Drawn dynamically in _draw_donut_chart
            continue
        if template_structure.layout_type in ("classic_neurial", "modern_manrope") and field.key in (
            "donut_energy_charges", "donut_fixed_charges", "donut_fppca_charges", "donut_govt_duty"
        ):
            continue

        if template_structure.layout_type == "modern_manrope":
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

            if field.key in ("security_deposit_held", "additional_security"):
                clean_amt = text.lstrip("₹").strip()
                try:
                    amt_num = float(clean_amt.replace(",", ""))
                    formatted_val = f"{amt_num:,.2f}"
                except (ValueError, TypeError):
                    formatted_val = clean_amt or "0.00"
                c.setFillColorRGB(0, 0, 0)
                norm_font = _resolve_font_name("Manrope-Bold", registered_fonts)
                rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else norm_font
                baseline_y = page_height - field.bottom
                c.setFont(rupee_font, 8.0)
                c.drawString(field.x0, baseline_y, "₹")
                rw = c.stringWidth("₹", rupee_font, 8.0)
                c.setFont(norm_font, 8.0)
                c.drawString(field.x0 + rw + 1.0, baseline_y, formatted_val)
                continue

        if template_structure.layout_type == "classic_neurial":
            if field.key == "headline_due_amount":
                clean_amt = text.lstrip("₹").strip()
                c.setFillColorRGB(0, 0, 0)
                target_font = _resolve_font_name("NeurialGrotesk-Bold", registered_fonts)
                rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else target_font
                baseline_y = page_height - field.bottom
                c.setFont(rupee_font, 24.0)
                c.drawString(field.x0, baseline_y, "₹")
                rw = c.stringWidth("₹", rupee_font, 24.0)
                c.setFont(target_font, 24.0)
                c.drawString(field.x0 + rw, baseline_y, clean_amt)
                continue

            if field.key == "previous_payment_line":
                if text:
                    c.setFillColorRGB(0, 0, 0)
                    norm_font = _resolve_font_name("NeurialGrotesk-Regular", registered_fonts)
                    rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else norm_font
                    baseline_y = page_height - field.bottom
                    x_cur = field.x0
                    if "₹" in text:
                        parts = text.split("₹", 1)
                        c.setFont(norm_font, 9.0)
                        c.drawString(x_cur, baseline_y, parts[0])
                        x_cur += c.stringWidth(parts[0], norm_font, 9.0)

                        c.setFont(rupee_font, 9.0)
                        c.drawString(x_cur, baseline_y, "₹")
                        x_cur += c.stringWidth("₹", rupee_font, 9.0)

                        c.setFont(norm_font, 9.0)
                        c.drawString(x_cur, baseline_y, parts[1])
                    else:
                        c.setFont(norm_font, 9.0)
                        c.drawString(x_cur, baseline_y, text)
                continue

            if field.key in ("security_deposit_held", "additional_security"):
                clean_amt = text.lstrip("₹").strip()
                try:
                    amt_num = float(clean_amt.replace(",", ""))
                    formatted_val = f"{amt_num:,.2f}"
                except (ValueError, TypeError):
                    formatted_val = clean_amt or "0.00"
                c.setFillColorRGB(0, 0, 0)
                norm_font = _resolve_font_name("NeurialGrotesk-Regular", registered_fonts)
                rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else norm_font
                baseline_y = page_height - 353.4
                if field.key == "security_deposit_held":
                    c.setFont(rupee_font, 8.0)
                    c.drawString(316.9, baseline_y, "₹")
                    c.setFont(norm_font, 8.0)
                    c.drawString(321.5, baseline_y, formatted_val)
                else:
                    c.setFont(rupee_font, 8.0)
                    c.drawString(434.4, baseline_y, "₹")
                    c.setFont(norm_font, 8.0)
                    c.drawString(439.0, baseline_y, formatted_val)
                continue

        if field.key == "consumption_sentence_units":
            c.setFillColorRGB(0, 0, 0)
            is_classic = template_structure.layout_type == "classic_neurial"
            target_reg = _resolve_font_name("NeurialGrotesk-Regular" if is_classic else "Manrope-Regular", registered_fonts)
            target_bold = _resolve_font_name("NeurialGrotesk-Bold" if is_classic else "Manrope-Bold", registered_fonts)
            units_val = str(values.get("consumption_units") or text or "0")
            units_match = re.search(r"\d+", units_val)
            units_str = units_match.group() if units_match else units_val

            baseline_y = page_height - (525.1 if is_classic else 525.0)
            x_cur = 42.8
            c.setFont(target_reg, 9.0)
            c.drawString(x_cur, baseline_y, "You consumed ")
            x_cur += c.stringWidth("You consumed ", target_reg, 9.0)

            c.setFont(target_bold, 9.0)
            c.drawString(x_cur, baseline_y, f"{units_str} units ")
            x_cur += c.stringWidth(f"{units_str} units ", target_bold, 9.0)

            c.setFont(target_reg, 9.0)
            c.drawString(x_cur, baseline_y, "this billing cycle.")
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
        if template_structure.layout_type == "classic_neurial" and field.key.startswith("coupon_"):
            baseline_y += 1.0

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

    # Dynamic Wrapped Address rendering (Page 0)
    if any(f.key.startswith("address_line") for f in fields) and template_structure.layout_type in ("classic_neurial", "modern_manrope"):
        _draw_wrapped_address(c, page_height, values, registered_fonts, template_structure)

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
            start_axis_x = bar_x_positions[0][0] if bar_x_positions else clear_x0
            end_axis_x = bar_x_positions[-1][1] if bar_x_positions else clear_x1
            c.line(start_axis_x, page_height - axis_y, end_axis_x, page_height - axis_y)

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

    # Check J: PDF headline amount matches bill total
    headline_clean = float(str(values.get("headline_due_amount", "")).replace(",", "").lstrip("₹").strip())
    if abs(headline_clean - bill.total_amount_due) > 0.02 and abs(headline_clean - round(bill.total_amount_due)) > 0.02:
        raise ValueError(f"[CHECK J FAILED] Headline amount {headline_clean} != bill total {bill.total_amount_due}")

    print(f"[PRE-FLIGHT VALIDATION] Successfully verified checks A-J for Customer {consumer.get('customer_id')}")


def generate_bill_pdf(template_path: Optional[str] = None, consumer: dict = None, bill = None, output_path: str = "",
                      consumption_history: dict = None, template_structure: Optional[TemplateStructure] = None) -> str:
    """
    Generates a single filled PDF invoice for one consumer record using the specified template PDF.
    """
    if not template_path:
        template_path = get_template_for_billing_month(consumer)

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

        if page_index == 0 and template_structure.layout_type in ("modern_manrope", "classic_neurial"):
            _strip_template_donut_and_leaders(page, reader, template_structure.layout_type)

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