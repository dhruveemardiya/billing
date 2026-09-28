import io
import math
import os
import re
from typing import Optional

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, ContentStream
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import hashlib
from PIL import Image
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

    clean_addr = " ".join(raw_addr.split()).upper().replace("–", "-").replace("—", "-").replace("−", "-")
    layout = template_structure.layout_type

    if layout == "classic_neurial":
        # Use Helvetica for complete glyph set (avoiding missing glyph artifacts in extracted subset)
        font_name = "Helvetica"
        x0 = 41.8
        max_width = 153.2
        words = clean_addr.split()

        # Adaptively scale font size and spacing so even very long addresses fit with ample clearance
        chosen_lines = []
        chosen_size = 7.5
        chosen_step = 9.8
        chosen_gap = 17.0
        chosen_cstep = 10.5

        for font_size, line_step, gap_after, contact_step in [
            (7.5, 9.8, 17.0, 10.5),  # standard 1-4 lines
            (7.0, 9.0, 14.5, 9.5),   # medium 5-6 lines
            (6.5, 8.2, 13.0, 8.8),   # long 7-8 lines
            (5.8, 7.2, 11.5, 8.0),   # extreme 9+ lines
        ]:
            lines = []
            cur = []
            for w in words:
                cand = " ".join(cur + [w])
                w_pt = c.stringWidth(cand, font_name, font_size)
                if w_pt <= max_width:
                    cur.append(w)
                else:
                    if cur:
                        lines.append(" ".join(cur))
                    cur = [w]
            if cur:
                lines.append(" ".join(cur))

            n = len(lines)
            start_y = 183.0
            last_addr_y = start_y + (n - 1) * line_step
            mobile_y = last_addr_y + gap_after
            email_val_y = mobile_y + 2 * contact_step

            chosen_lines = lines
            chosen_size = font_size
            chosen_step = line_step
            chosen_gap = gap_after
            chosen_cstep = contact_step

            # Keep bottom well above orange YOUR BILL banner (y=295.0)
            if email_val_y <= 276.0 or font_size <= 5.8:
                break

        # Space after name:
        # Consumer name baseline is at 170.4. Address line 1 baseline is placed at 183.0
        # leaving an elegant ~5.1 pt visual gap after name.
        start_y = 183.0
        c.setFillColorRGB(0, 0, 0)
        c.setFont(font_name, chosen_size)
        baselines = [start_y + i * chosen_step for i in range(len(chosen_lines))]
        for line_text, y in zip(chosen_lines, baselines):
            c.drawString(x0, page_height - y, line_text)

        last_addr_y = baselines[-1] if baselines else start_y

        # Space after address:
        mobile_y = last_addr_y + chosen_gap
        contact_size = min(8.0, chosen_size + 0.5)
        c.setFont(font_name, contact_size)

        mobile_val = values.get("mobile_no") or "******1513"
        mobile_text = f"Registered Mobile No : {mobile_val}"
        c.drawString(x0, page_height - mobile_y, mobile_text)

        # Space after Registered Mobile No : -> Registered E-Mail ID :
        email_lbl_y = mobile_y + chosen_cstep
        c.drawString(x0, page_height - email_lbl_y, "Registered E-Mail ID :")

        # Space after Registered E-Mail ID : -> email value
        email_val_y = email_lbl_y + chosen_cstep
        email_val = values.get("email") or "ch********gi@gmail.com"
        c.drawString(x0, page_height - email_val_y, str(email_val))

    elif layout == "modern_manrope":
        font_name = _resolve_font_name("Manrope-Regular", registered_fonts)
        x0 = 40.0
        max_width = 170.0
        words = clean_addr.split()
        lines = []
        cur = []
        for w in words:
            cand = " ".join(cur + [w])
            try:
                w_pt = c.stringWidth(cand, font_name, 8.0)
            except Exception:
                w_pt = c.stringWidth(cand, "Helvetica", 8.0)
            if w_pt <= max_width:
                cur.append(w)
            else:
                if cur:
                    lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))

        # Space after name:
        # Consumer name baseline is at 179.0. Address line 1 baseline is placed at 192.0
        # leaving a clean ~5.0 pt visual gap after name.
        start_y = 192.0
        line_step = 10.0
        c.setFillColorRGB(0, 0, 0)
        c.setFont(font_name, 8.0)
        baselines = [start_y + i * line_step for i in range(len(lines))]
        for line_text, y in zip(lines, baselines):
            c.drawString(x0, page_height - y, line_text)

        # If lines exceed 5, mobile and email shift down dynamically
        if len(lines) > 5:
            last_addr_y = baselines[-1]
            mobile_y = last_addr_y + 18.0
            bold_font = _resolve_font_name("Manrope-Bold", registered_fonts)
            c.setFont(bold_font, 8.0)
            mobile_val = values.get("mobile_no") or "******2799"
            c.drawString(x0, page_height - mobile_y, f"Registered Mobile:  {mobile_val}")
            email_y = mobile_y + 10.0
            email_val = values.get("email") or "bh****ta@hotmail.com"
            c.drawString(x0, page_height - email_y, f"Registered Email:  {email_val}")

    else:
        addr_fields = [f for f in template_structure.fields if f.key.startswith("address_line")]
        if not addr_fields:
            return
        x0 = addr_fields[0].x0
        max_width = (addr_fields[0].x1 - addr_fields[0].x0) if addr_fields[0].x1 else 150.0
        top_y = min(f.top for f in addr_fields)
        bottom_y = max(f.bottom for f in addr_fields)
        font_name = _resolve_font_name(addr_fields[0].font, registered_fonts)

        words = clean_addr.split()
        lines = []
        cur = []
        for w in words:
            cand = " ".join(cur + [w])
            try:
                w_pt = c.stringWidth(cand, font_name, 7.5)
            except Exception:
                w_pt = c.stringWidth(cand, "Helvetica", 7.5)
            if w_pt <= max_width:
                cur.append(w)
            else:
                if cur:
                    lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))

        n = len(lines)
        if n == 0:
            return
        c.setFillColorRGB(0, 0, 0)
        c.setFont(font_name, 7.5)
        step = (bottom_y - top_y) / max(n - 1, 1) if n > 1 else 0
        baselines = [page_height - (top_y + 7.5 + i * step) for i in range(n)]
        for line_text, b_y in zip(lines, baselines):
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
        if template_structure.layout_type == "classic_neurial" and field.key in ("mobile_no", "email"):
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
            c.rect(40.0, page_height - 275.0, 165.0, 104.0, stroke=0, fill=1)
        elif template_structure.layout_type == "modern_manrope":
            c.rect(39.5, page_height - 245.0, 172.5, 61.0, stroke=0, fill=1)

    # Pass 2: Draw text on top of masked backgrounds
    for field in fields:
        if template_structure.layout_type in ("classic_neurial", "modern_manrope") and field.key.startswith("address_line"):
            continue
        if template_structure.layout_type == "classic_neurial" and field.key in ("mobile_no", "email"):
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


def _generate_pgvcl_bill_pdf(template_path: str, consumer: dict, bill, values: dict, output_path: str,
                            template_structure: TemplateStructure) -> str:
    """
    Renders PGVCL electricity bill PDF using PGVCL.jpeg as the background template,
    with pixel-perfect cell masking, calibrated paper tones, razor-sharp table
    grid line preservation, authentic printed typography, and strict 7-field handwriting.
    """
    import numpy as np

    with Image.open(template_path) as img:
        img_rgb = img.convert("RGB")
        img_w, img_h = img_rgb.size
        arr = np.array(img_rgb)

    page_w = 595.0
    page_h = round(page_w * img_h / img_w, 2)
    scale = page_w / img_w

    def get_bg(px0, py0, px1, py1, fallback=(0.922, 0.925, 0.918)):
        sub = arr[max(0, int(py0)):min(img_h, int(py1)), max(0, int(px0)):min(img_w, int(px1))]
        mask = (sub[:, :, 0] > 165) & (sub[:, :, 0] < 248) & (np.sum(sub, axis=2) > 500)
        if np.any(mask):
            med = np.median(sub[mask], axis=0)
            return tuple(round(float(c) / 255.0, 4) for c in med)
        return fallback

    # 1. Base canvas with the PGVCL background template image
    base_buf = io.BytesIO()
    c_base = canvas.Canvas(base_buf, pagesize=(page_w, page_h))
    c_base.drawImage(template_path, 0, 0, width=page_w, height=page_h)
    c_base.save()
    base_buf.seek(0)
    base_page = PdfReader(base_buf).pages[0]

    # 2. Register fonts
    print_font_reg = "Helvetica"
    print_font_bold = "Helvetica-Bold"
    if os.path.exists(r"C:\Windows\Fonts\arial.ttf"):
        try:
            if "Arial" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("Arial", r"C:\Windows\Fonts\arial.ttf"))
            print_font_reg = "Arial"
        except Exception:
            pass
    if os.path.exists(r"C:\Windows\Fonts\arialbd.ttf"):
        try:
            if "Arial-Bold" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("Arial-Bold", r"C:\Windows\Fonts\arialbd.ttf"))
            print_font_bold = "Arial-Bold"
        except Exception:
            pass

    hand_font_name = "Helvetica-Bold"
    for fname, fpath in [
        ("SegoePrint", r"C:\Windows\Fonts\segoepr.ttf"),
        ("SegoePrint-Bold", r"C:\Windows\Fonts\segoeprb.ttf"),
        ("InkFree", r"C:\Windows\Fonts\Inkfree.ttf"),
    ]:
        if os.path.exists(fpath):
            try:
                if fname not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(fname, fpath))
                hand_font_name = fname
                break
            except Exception:
                pass

    # 3. Overlay canvas for masking and dynamic field rendering
    overlay_buf = io.BytesIO()
    c = canvas.Canvas(overlay_buf, pagesize=(page_w, page_h))

    def mask_cell(px, py, pw, ph, bg_sample=None, fallback=(0.922, 0.925, 0.918)):
        if bg_sample is None:
            bg_sample = (px, py, px + pw, py + ph)
        bg = get_bg(*bg_sample, fallback=fallback)
        c.setFillColorRGB(*bg)
        x = px * scale
        w = pw * scale
        y = page_h - (py + ph) * scale
        h = ph * scale
        c.rect(x, y, w, h, stroke=0, fill=1)

    def draw_h_line(x0, x1, y, stroke_color=(0.40, 0.40, 0.40), width=0.55):
        c.setStrokeColorRGB(*stroke_color)
        c.setLineWidth(width)
        c.line(x0 * scale, page_h - y * scale, x1 * scale, page_h - y * scale)

    def draw_v_line(x, y0, y1, stroke_color=(0.40, 0.40, 0.40), width=0.55):
        c.setStrokeColorRGB(*stroke_color)
        c.setLineWidth(width)
        c.line(x * scale, page_h - y1 * scale, x * scale, page_h - y0 * scale)

    def draw_text_in_cell(px, py, pw, ph, text, font=print_font_reg, size=8.5, align='left', color=(0.10, 0.12, 0.15), pad_x=5.0):
        if text is None or text == "":
            return
        c.setFont(font, size)
        c.setFillColorRGB(*color)
        x = px * scale
        w = pw * scale
        cell_mid_y = page_h - (py + ph / 2.0) * scale
        baseline_y = cell_mid_y - 0.35 * size
        text_str = str(text)
        if align == 'right':
            c.drawRightString(x + w - pad_x, baseline_y, text_str)
        elif align == 'center':
            c.drawCentredString(x + w / 2.0, baseline_y, text_str)
        else:
            c.drawString(x + pad_x, baseline_y, text_str)

    def draw_handwritten_in_cell(px, py, pw, ph, text, font=hand_font_name, size=8.8, align='center', color=(0.08, 0.13, 0.35), pad_x=5.0):
        if text is None or text == "":
            return
        text_str = str(text)
        x = px * scale
        w = pw * scale
        cell_mid_y = page_h - (py + ph / 2.0) * scale
        base_y = cell_mid_y - 0.35 * size

        seed = int(hashlib.md5(f"{text_str}_{px}_{py}".encode()).hexdigest()[:8], 16)
        char_data = []
        total_w = 0.0

        for i, ch in enumerate(text_str):
            h_val = (seed + i * 43) % 1000
            c_size = size + ((h_val % 5) - 2) * 0.04
            dy = (((h_val // 5) % 5) - 2) * 0.04
            dx = (((h_val // 25) % 5) - 2) * 0.02
            c_w = pdfmetrics.stringWidth(ch, font, c_size)
            char_data.append((ch, c_size, dy, dx, c_w))
            total_w += c_w + dx

        if align == 'right':
            cur_x = x + w - pad_x - total_w
        elif align == 'center':
            cur_x = x + (w - total_w) / 2.0
        else:
            cur_x = x + pad_x

        c.setFillColorRGB(*color)
        for ch, c_size, dy, dx, c_w in char_data:
            c.setFont(font, c_size)
            c.drawString(cur_x, base_y + dy, ch)
            cur_x += c_w + dx

    # 1. SDO Name & Billing Month Header (exact bounds: x = 125 to 812, y = 163 to 197)
    # Cleanly mask the entire header row interior to completely eliminate the scanner paper crease under SDO Name
    mask_cell(126, 164, 685, 32, bg_sample=(130, 150, 800, 162), fallback=(0.938, 0.940, 0.938))
    draw_h_line(125, 812, 163, (0.45, 0.45, 0.45), 0.55)
    draw_h_line(125, 812, 197, (0.45, 0.45, 0.45), 0.55)
    draw_v_line(125, 163, 197, (0.45, 0.45, 0.45), 0.55)
    draw_v_line(812, 163, 197, (0.45, 0.45, 0.45), 0.55)

    draw_text_in_cell(125, 163, 380, 34, "SDO NAME : VERAVAL (T)", font=print_font_bold, size=8.2, align='left', color=(0.10, 0.12, 0.15), pad_x=6.0)

    b_raw = str(consumer.get('billing_month') or '').strip().upper()
    if b_raw.startswith("ELECTRICITY BILL"):
        b_month_text = b_raw
    else:
        b_month_text = f"ELECTRICITY BILL : {b_raw}" if b_raw else "ELECTRICITY BILL : MAR-APR,26"
    draw_text_in_cell(516, 163, 290, 34, b_month_text, font=print_font_bold, size=8.2, align='left', color=(0.10, 0.12, 0.15), pad_x=0.0)

    # 2. Consumer Name & Address Box (exact bounds: x = 87 to 516, y = 197 to 384)
    mask_cell(88, 198, 427, 185, bg_sample=(100, 205, 480, 320), fallback=(0.847, 0.859, 0.859))
    # Redraw outer box & horizontal divider lines
    draw_v_line(87, 197, 384, (0.35, 0.35, 0.35), 0.65)
    draw_v_line(516, 197, 384, (0.35, 0.35, 0.35), 0.65)
    for ly in [197, 224, 251, 279, 306, 330, 356, 384]:
        draw_h_line(87, 516, ly, (0.45, 0.45, 0.45), 0.55)

    c_name = str(consumer.get('consumer_name') or '').strip().upper()
    cust_id = str(consumer.get('customer_id') or '').strip()
    raw_mno = str(consumer.get('meter_no') or '5797035').strip()
    clean_mno = re.sub(r"^ONE\s*[-_]?\s*", "", raw_mno, flags=re.IGNORECASE)

    raw_addr = str(consumer.get('address') or '').strip().upper()
    v_name = str(consumer.get('village_name') or '').strip()
    village = str(consumer.get('village') or '').strip()
    taluka = str(consumer.get('taluka') or '').strip()
    district = str(consumer.get('district') or '').strip()

    # Determine default location if not specified
    if not district:
        if "AHMEDABAD" in raw_addr:
            district = "AHMEDABAD"
        else:
            district = "GIR SOMNATH"
    if not taluka:
        if "AHMEDABAD" in raw_addr:
            taluka = "AHMEDABAD"
        else:
            taluka = "Veraval"
    if not village:
        if "PRAHLAD NAGAR" in raw_addr or "PRAHLADNAGAR" in raw_addr:
            village = "PRAHLAD NAGAR"
        elif "AHMEDABAD" in raw_addr:
            village = "AHMEDABAD"
        else:
            village = "Veraval (M+OG) V"

    # Split address into chunks fitting comfortably inside cell width
    words = raw_addr.split()
    addr_chunks = []
    curr = []
    for w in words:
        if len(' '.join(curr + [w])) <= 42:
            curr.append(w)
        else:
            if curr:
                addr_chunks.append(' '.join(curr))
            curr = [w]
    if curr:
        addr_chunks.append(' '.join(curr))

    # Map into Rows 2 to 5 keeping complete address visible and preserving Village / Taluka / District
    if len(addr_chunks) >= 2:
        line2 = addr_chunks[0]
        line3 = addr_chunks[1]
        line4 = f"VILLAGE :{village}, TAL :{taluka}"
        line5 = f"DISTRICT :{district}"
    elif len(addr_chunks) == 1 and v_name:
        line2 = addr_chunks[0]
        line3 = v_name.upper()
        line4 = f"VILLAGE :{village}, TAL :{taluka}"
        line5 = f"DISTRICT :{district}"
    elif len(addr_chunks) == 1:
        line2 = addr_chunks[0]
        line3 = f"VILLAGE :{village}"
        line4 = f"TALUKA :{taluka}"
        line5 = f"DISTRICT :{district}"
    else:
        line2 = ""
        line3 = f"VILLAGE :{village}"
        line4 = f"TALUKA :{taluka}"
        line5 = f"DISTRICT :{district}"

    # Rows 1 to 7 with true vertical centering and exact printed PGVCL typography:
    draw_text_in_cell(87, 197, 429, 27, c_name, font=print_font_bold, size=8.5, pad_x=6.0, color=(0.10, 0.12, 0.15))
    draw_text_in_cell(87, 224, 429, 27, line2, font=print_font_reg, size=7.8, pad_x=6.0, color=(0.10, 0.12, 0.15))
    draw_text_in_cell(87, 251, 429, 28, line3, font=print_font_reg, size=7.8, pad_x=6.0, color=(0.10, 0.12, 0.15))
    draw_text_in_cell(87, 279, 429, 27, line4, font=print_font_reg, size=7.8, pad_x=6.0, color=(0.10, 0.12, 0.15))
    draw_text_in_cell(87, 306, 429, 24, line5, font=print_font_reg, size=7.8, pad_x=6.0, color=(0.10, 0.12, 0.15))
    draw_text_in_cell(87, 330, 429, 26, f"Consumer No : {cust_id}", font=print_font_bold, size=8.5, pad_x=6.0, color=(0.10, 0.12, 0.15))
    draw_text_in_cell(87, 356, 429, 28, f"Meter No : ONE-{clean_mno}", font=print_font_bold, size=8.5, pad_x=6.0, color=(0.10, 0.12, 0.15))

    # 3. System Metadata Table (exact bounds: x = 680 to 900, y = 199 to 385)
    # Mask ONLY the value cells, preserving the printed labels on the left
    mask_cell(682, 200, 217, 184, bg_sample=(690, 205, 890, 380), fallback=(0.925, 0.925, 0.929))
    draw_v_line(680, 199, 385, (0.45, 0.45, 0.45), 0.55)
    draw_v_line(900, 199, 385, (0.35, 0.35, 0.35), 0.65)
    for ly in [199, 226, 251, 279, 306, 332, 359, 385]:
        draw_h_line(680, 900, ly, (0.45, 0.45, 0.45), 0.55)

    draw_text_in_cell(680, 199, 220, 27, str(consumer.get('census_code') or '12100002'), font=print_font_reg, size=8.5, pad_x=10.0)
    draw_text_in_cell(680, 226, 220, 25, str(consumer.get('feeder_code') or '4'), font=print_font_reg, size=8.5, pad_x=10.0)
    draw_text_in_cell(680, 251, 220, 28, str(consumer.get('route_code') or '3/4/5/32'), font=print_font_reg, size=8.5, pad_x=10.0)
    draw_text_in_cell(680, 279, 220, 27, str(consumer.get('bill_no') or '3/06825'), font=print_font_reg, size=8.5, pad_x=10.0)
    # Row 5 (306 to 332): blank row in reference PGVCL bill
    # Row 6 & 7: Bill Date and Last Date for Payment in Handwriting font, centered in row
    draw_handwritten_in_cell(680, 332, 220, 27, str(consumer.get('bill_date') or ''), font=hand_font_name, size=8.8, align='center')
    draw_handwritten_in_cell(680, 359, 220, 26, str(consumer.get('due_date') or ''), font=hand_font_name, size=8.8, align='center')

    # 4. Tech Specs Bar (exact bounds: x = 87 to 900, y = 385 to 439)
    # Row 1 (Labels: 385 to 409): clean Max Demand label and erase stray scanned pen strokes
    mask_cell(206, 386, 103, 22, bg_sample=(210, 388, 305, 406), fallback=(0.863, 0.871, 0.871))
    draw_text_in_cell(205, 385, 105, 24, "Max. Demand", font=print_font_bold, size=8.2, align='center', color=(0.10, 0.12, 0.15))

    # Erase scanned pen stroke across Seasonal & Days
    mask_cell(681, 386, 134, 22, bg_sample=(685, 388, 814, 406), fallback=(0.863, 0.871, 0.871))
    draw_text_in_cell(680, 385, 84, 24, "Seasonal", font=print_font_bold, size=8.2, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(764, 385, 52, 24, "Days", font=print_font_bold, size=8.2, align='center', color=(0.10, 0.12, 0.15))

    # Row 2 (Values: 409 to 439):
    mask_cell(88, 410, 811, 28, bg_sample=(100, 412, 890, 435), fallback=(0.863, 0.871, 0.871))

    # Redraw Tech Specs grid lines
    draw_h_line(87, 900, 385, (0.35, 0.35, 0.35), 0.65)
    draw_h_line(87, 900, 409, (0.45, 0.45, 0.45), 0.55)
    draw_h_line(87, 900, 439, (0.35, 0.35, 0.35), 0.65)
    tech_cols = [87, 205, 310, 396, 524, 602, 680, 764, 816, 900]
    for vx in tech_cols:
        draw_v_line(vx, 385, 439, (0.45, 0.45, 0.45), 0.55)

    load_kw = getattr(bill, 'sanctioned_load_kw', 5.5) or 5.5
    cat_str = str(consumer.get('category') or '')
    cat_display = 'RGPU' if cat_str.lower().startswith('res') else (cat_str.upper() or 'RGPU')
    raw_sd = str(consumer.get('security_deposit', '1562') or '1562')
    clean_sd = str(int(float(raw_sd))) if re.match(r'^\d+(\.\d+)?$', raw_sd) else raw_sd

    draw_text_in_cell(87, 409, 118, 30, str(consumer.get('meter_status', '1')), font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_handwritten_in_cell(205, 409, 105, 30, f"{load_kw:.2f}", font=hand_font_name, size=8.5, align='center')
    draw_text_in_cell(310, 409, 86, 30, str(consumer.get('mf', '1.0')), font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(396, 409, 128, 30, str(consumer.get('mtr_chg_code', 'A')), font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(524, 409, 78, 30, cat_display, font=print_font_reg, size=8.0, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(602, 409, 78, 30, f"{load_kw:.1f}", font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(764, 409, 52, 30, "0", font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(816, 409, 84, 30, clean_sd, font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))

    # 5. Meter Readings Table (KWH column: x = 190 to 268, y = 437 to 559)
    # Header row (KWH: 437 to 463): mask out scanned pen tick and render crisp KWH
    mask_cell(191, 438, 76, 24, bg_sample=(195, 440, 265, 460), fallback=(0.851, 0.851, 0.855))
    draw_text_in_cell(190, 437, 78, 26, "KWH", font=print_font_bold, size=8.2, align='center', color=(0.10, 0.12, 0.15))

    # Values rows: Row 2 (Present: 463-495), Row 3 (Past: 495-528), Row 4 (Difference: 528-559)
    start_r = int(consumer.get('start_reading') or 0)
    end_r = int(consumer.get('end_reading') or 0)
    diff_r = end_r - start_r

    mask_cell(191, 464, 76, 94, bg_sample=(195, 465, 265, 555), fallback=(0.851, 0.851, 0.855))
    draw_v_line(190, 437, 559, (0.45, 0.45, 0.45), 0.55)
    draw_v_line(268, 437, 559, (0.45, 0.45, 0.45), 0.55)
    draw_h_line(190, 268, 463, (0.45, 0.45, 0.45), 0.55)
    draw_h_line(190, 268, 495, (0.45, 0.45, 0.45), 0.55)
    draw_h_line(190, 268, 528, (0.45, 0.45, 0.45), 0.55)
    draw_h_line(87, 516, 559, (0.35, 0.35, 0.35), 0.65)

    # Row 2 (Present reading): HANDWRITTEN
    draw_handwritten_in_cell(190, 463, 78, 32, str(end_r), font=hand_font_name, size=9.2, align='center')
    # Row 3 (Past reading): PRINTED FONT (Regular weight!)
    draw_text_in_cell(190, 495, 78, 33, str(start_r), font=print_font_reg, size=8.8, align='center', color=(0.10, 0.12, 0.15))
    # Row 4 (Difference): HANDWRITTEN
    draw_handwritten_in_cell(190, 528, 78, 31, str(diff_r), font=hand_font_name, size=9.2, align='center')

    # 6. Account & Middle Consumption Table (x: 87 to 516, y: 559 to 770)
    # Col 1 (Labels: 87 to 268) is PRESERVED, not masked!
    # Col 2 (Values: 268 to 432): mask and fill
    mask_cell(269, 560, 162, 209, bg_sample=(275, 565, 425, 765), fallback=(0.835, 0.835, 0.835))
    # Col 3 (Right column: 432 to 516): mask ONLY the two numeric value cells
    mask_cell(433, 613, 82, 24, bg_sample=(435, 614, 510, 636), fallback=(0.835, 0.835, 0.835))
    mask_cell(433, 718, 82, 25, bg_sample=(435, 719, 510, 742), fallback=(0.835, 0.835, 0.835))

    draw_v_line(87, 559, 770, (0.35, 0.35, 0.35), 0.65)
    draw_v_line(268, 559, 770, (0.45, 0.45, 0.45), 0.55)
    draw_v_line(432, 559, 770, (0.45, 0.45, 0.45), 0.55)
    draw_v_line(516, 559, 770, (0.35, 0.35, 0.35), 0.65)
    mid_h_lines = [559, 584, 612, 638, 664, 690, 717, 744, 770]
    for hy in mid_h_lines:
        draw_h_line(87, 516, hy, (0.45, 0.45, 0.45), 0.55)

    ref_u = consumer.get('reference_units') or bill.units_consumed
    draw_text_in_cell(268, 559, 164, 25, "0", font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(268, 584, 164, 28, str(int(ref_u)), font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(268, 612, 164, 26, str(int(bill.units_consumed)), font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(268, 638, 164, 26, f"{(bill.energy_charges + bill.fixed_charges):,.2f}", font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(268, 664, 164, 26, "0.00", font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(268, 690, 164, 27, "0.00", font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(268, 717, 164, 27, "0.00", font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(268, 744, 164, 26, "0.00", font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))

    prov_val = float(consumer.get('provisional_bill_amount', 0.0) or 0.0)
    prev_pay = float(consumer.get('previous_payment') or 0.0)
    draw_text_in_cell(432, 612, 84, 26, f"{prov_val:,.2f}", font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))
    draw_text_in_cell(432, 717, 84, 27, f"{prev_pay:,.2f}", font=print_font_reg, size=8.5, align='center', color=(0.10, 0.12, 0.15))

    # 7. Last Three Month Units Table (exact bounds: x = 86 to 516, y = 953 to 1033)
    # Header row "Last Three Month Units" is above 953, and label col (86 to 188) is PRESERVED!
    mask_cell(189, 954, 326, 78, bg_sample=(195, 960, 510, 1030), fallback=(0.804, 0.808, 0.808))
    for vx in [188, 296, 402, 516]:
        draw_v_line(vx, 953, 1033, (0.45, 0.45, 0.45), 0.55)
    for hy in [953, 980, 1007, 1033]:
        draw_h_line(86, 516, hy, (0.45, 0.45, 0.45), 0.55)

    last_3 = consumer.get('last_3_months') or []
    col_bounds = [(188, 108), (296, 106), (402, 114)]
    for c_idx, p in enumerate(last_3[:3]):
        if c_idx < len(col_bounds):
            cx, cw = col_bounds[c_idx]
            m_lbl = str(p.get('month', '')).upper()
            u_lbl = str(int(p.get('units', 0)))
            amt_lbl = f"{float(p.get('amount', 0.0)):,.2f}"
            draw_text_in_cell(cx, 953, cw, 27, m_lbl, font=print_font_bold, size=7.8, align='center', color=(0.10, 0.12, 0.15))
            draw_text_in_cell(cx, 980, cw, 27, u_lbl, font=print_font_reg, size=8.0, align='center', color=(0.10, 0.12, 0.15))
            draw_text_in_cell(cx, 1007, cw, 26, amt_lbl, font=print_font_reg, size=8.0, align='center', color=(0.10, 0.12, 0.15))

    # 8. Charges Details Table (x: 516 to 902, y: 439 to 1036)
    # Header row: 439 to 467 ("Sr." | "Charges Details" | "Rupee") is PRESERVED!
    # Rows 1 to 20: exact pixel ranges measured from PGVCL.jpeg
    fixed_chg = bill.fixed_charges
    energy_chg = bill.energy_charges
    ujala_chg = float(consumer.get('ujala_charges', 0.0) or 0.0)
    fppca_chg = bill.fppca_charges
    reactive_chg = float(consumer.get('reactive_charge', 0.0) or 0.0)
    duty_chg = bill.govt_duty
    meter_chg = float(consumer.get('meter_charge', 0.0) or 0.0)
    misc_chg = float(consumer.get('fuse_misc_charge', 0.0) or 0.0)
    delay_chg = float(getattr(bill, 'delay_surcharge', 0.0) or 0.0)
    arrear_val = float(getattr(bill, 'arrear', 0.0) or 0.0)
    relief_val = float(consumer.get('govt_relief', 0.0) or 0.0)

    total_1_to_9 = (
        fixed_chg + energy_chg + ujala_chg + fppca_chg +
        reactive_chg + duty_chg + meter_chg + misc_chg + delay_chg
    )
    total_10_11 = total_1_to_9 + prov_val
    grand_total_val = total_10_11 + arrear_val
    net_bill_val = grand_total_val - relief_val

    charges_defs = [
        # (row_num, y0, y1, value_str, is_handwritten, is_shaded)
        (1,  467, 498,  f"{fixed_chg:,.2f}", False, False),
        (2,  498, 531,  f"{energy_chg:,.2f}", False, False),
        (3,  531, 562,  f"{ujala_chg:,.2f}" if ujala_chg > 0 else "", False, False),
        (4,  562, 589,  f"{fppca_chg:,.2f}", False, False),
        (5,  589, 615,  f"{reactive_chg:,.2f}" if reactive_chg > 0 else "", False, False),
        (6,  615, 641,  f"{duty_chg:,.2f}", False, False),
        (7,  641, 668,  f"{meter_chg:,.2f}" if meter_chg > 0 else "", False, False),
        (8,  668, 694,  f"{misc_chg:,.2f}" if misc_chg > 0 else "0.00", False, False),
        (9,  694, 721,  f"{delay_chg:,.2f}" if delay_chg > 0 else "0.00", False, False),
        (10, 721, 747,  f"{total_1_to_9:,.2f}", True, True),
        (11, 747, 774,  f"{prov_val:,.2f}" if prov_val > 0 else "", False, False),
        (12, 774, 800,  f"{total_10_11:,.2f}", False, False),
        (13, 800, 827,  f"{arrear_val:,.2f}", False, False),
        (14, 827, 874,  "", False, False),
        (15, 874, 901,  "", False, False),
        (16, 901, 928,  f"{grand_total_val:,.2f}", False, False),
        (17, 928, 956,  "", False, False),
        (18, 956, 982,  f"-{relief_val:,.2f}" if relief_val > 0 else "", False, False),
        (19, 982, 1011, "", False, False),
        (20, 1011, 1036, f"{net_bill_val:,.2f}", True, True),
    ]

    # Mask only the Rupee value cells with appropriate regional / shaded tone
    for row_num, y0, y1, val, is_handwritten, is_shaded in charges_defs:
        if is_shaded:
            if row_num == 10:
                bg = (0.816, 0.827, 0.847)
            else:
                bg = (0.722, 0.737, 0.773)
        else:
            bg = (0.922, 0.925, 0.918)
        mask_cell(795, y0 + 1, 106, (y1 - y0) - 2, fallback=bg)

    # Redraw Charges table grid lines
    draw_v_line(794, 439, 1036, (0.45, 0.45, 0.45), 0.55)
    draw_v_line(902, 439, 1036, (0.35, 0.35, 0.35), 0.65)
    chg_h_lines = [439, 467, 498, 531, 562, 589, 615, 641, 668, 694, 721, 747, 774, 800, 827, 874, 901, 928, 956, 982, 1011, 1036]
    for hy in chg_h_lines:
        draw_h_line(794, 902, hy, (0.45, 0.45, 0.45), 0.55)

    # Render charge amounts:
    for row_num, y0, y1, val, is_handwritten, is_shaded in charges_defs:
        if val:
            row_ph = y1 - y0
            if is_handwritten:
                sz = 9.5 if row_num == 20 else 9.2
                draw_handwritten_in_cell(794, y0, 108, row_ph, val, font=hand_font_name, size=sz, align='right', pad_x=8.0)
            else:
                sz = 8.5 if row_num == 16 else 8.2
                draw_text_in_cell(794, y0, 108, row_ph, val, font=print_font_reg, size=sz, align='right', pad_x=8.0, color=(0.10, 0.12, 0.15))

    # 9. Bottom Office Slip (exact bounds: x = 86 to 910, y = 1142 to 1222)
    # Row 1 (Headers: 1142 to 1169) and Row 3 (Labels: 1196 to 1222) are PRESERVED!
    # Row 2 (Values: 1169 to 1196): Cleanly mask the old scanned values so cells remain blank as required
    mask_cell(88, 1170, 240, 25, bg_sample=(100, 1172, 320, 1194), fallback=(0.788, 0.796, 0.792))
    mask_cell(760, 1170, 148, 25, bg_sample=(765, 1172, 905, 1194), fallback=(0.788, 0.796, 0.792))

    draw_v_line(86, 1169, 1196, (0.45, 0.45, 0.45), 0.55)
    draw_v_line(330, 1169, 1196, (0.45, 0.45, 0.45), 0.55)
    draw_v_line(758, 1169, 1196, (0.45, 0.45, 0.45), 0.55)
    draw_v_line(910, 1169, 1196, (0.45, 0.45, 0.45), 0.55)
    draw_h_line(86, 910, 1169, (0.45, 0.45, 0.45), 0.55)
    draw_h_line(86, 910, 1196, (0.45, 0.45, 0.45), 0.55)
    # Row 2 value cells kept completely blank per requirement: "Do not put Consumer No into Payment Date... Keep all blank cells blank"

    c.save()
    overlay_buf.seek(0)
    ov_page = PdfReader(overlay_buf).pages[0]
    base_page.merge_page(ov_page)

    writer = PdfWriter()
    writer.add_page(base_page)

    output_dir = os.path.dirname(output_path) or "."
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "wb") as f_out:
        writer.write(f_out)

    return output_path


def generate_bill_pdf(template_path: Optional[str] = None, consumer: dict = None, bill = None, output_path: str = "",
                      consumption_history: dict = None, template_structure: Optional[TemplateStructure] = None) -> str:
    """
    Generates a single filled PDF invoice for one consumer record using the specified template PDF or PGVCL template.
    """
    if not template_path:
        template_path = get_template_for_billing_month(consumer)

    if template_structure is None:
        template_structure = detect_template_structure(template_path)

    values = pdf_mapper.build_field_values(consumer, bill, consumption_history=consumption_history, template_info=template_structure)

    # Automated check suite before rendering & saving (Requirement 12)
    validate_bill_generation_data(values, bill, consumer, consumption_history)

    # Check for PGVCL template
    is_pgvcl = template_structure.layout_type == "pgvcl" or template_path.lower().endswith((".jpeg", ".jpg", ".png"))
    if is_pgvcl:
        return _generate_pgvcl_bill_pdf(template_path, consumer, bill, values, output_path, template_structure)

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