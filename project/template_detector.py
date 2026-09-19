"""
template_detector.py
====================
Detects fields, variables, labels, coordinates, fonts, and background
masking colors from an uploaded Demo PDF template.

Supports:
1. DEMONEWPDF.pdf (new master template layout with Manrope typography)
2. demo.pdf (classic layout for backward compatibility)
3. Dynamic extraction for any future arbitrary PDF template
"""

import os
import re
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pdfplumber
import pypdfium2 as pdfium

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CLASSIC_TEMPLATE_PATH = os.path.join(PROJECT_DIR, "demo.pdf")
MODERN_TEMPLATE_PATH = os.path.join(PROJECT_DIR, "DEMONEWPDF.pdf")

MONTH_NAME_TO_NUM = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9, "sept": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def parse_billing_month_year(val) -> Tuple[Optional[int], Optional[int]]:
    """
    Extracts (month_num, year_num) where month_num is 1..12 and year_num is 4-digit int.
    Supports consumer dicts, (month, year) tuples, strings ('July 2026', '2026-08', etc.), and date objects.
    """
    if val is None:
        return None, None

    # 1. Consumer dict
    if isinstance(val, dict):
        for key in ("billing_month", "bill_date", "reading_date", "due_date"):
            raw = val.get(key)
            if raw:
                m, y = parse_billing_month_year(raw)
                if m is not None and y is not None:
                    return m, y
        return None, None

    # 2. Tuple / List: (month, year) or (year, month)
    if isinstance(val, (list, tuple)) and len(val) >= 2:
        v0, v1 = val[0], val[1]
        m, y = None, None
        if isinstance(v0, int) and 1 <= v0 <= 12 and isinstance(v1, int) and v1 > 1900:
            m, y = v0, v1
        elif isinstance(v1, int) and 1 <= v1 <= 12 and isinstance(v0, int) and v0 > 1900:
            y, m = v0, v1
        else:
            s0 = str(v0).strip().lower()
            if s0 in MONTH_NAME_TO_NUM:
                m = MONTH_NAME_TO_NUM[s0]
                try:
                    y = int(str(v1).strip())
                except ValueError:
                    pass
            else:
                s1 = str(v1).strip().lower()
                if s1 in MONTH_NAME_TO_NUM:
                    m = MONTH_NAME_TO_NUM[s1]
                    try:
                        y = int(str(v0).strip())
                    except ValueError:
                        pass
        if m is not None and y is not None:
            return m, y

    # 3. datetime / date object
    if hasattr(val, "year") and hasattr(val, "month"):
        return val.month, val.year

    # 4. String
    text = str(val).strip()
    if not text:
        return None, None

    # ISO format: YYYY-MM or YYYY/MM
    m_iso = re.search(r"^(\d{4})[\/\-](\d{1,2})$", text)
    if m_iso:
        y = int(m_iso.group(1))
        m = int(m_iso.group(2))
        if 1 <= m <= 12:
            return m, y

    # Slash/hyphen format: MM/YYYY or MM-YYYY
    m_slash = re.search(r"^(\d{1,2})[\/\-](\d{4})$", text)
    if m_slash:
        m = int(m_slash.group(1))
        y = int(m_slash.group(2))
        if 1 <= m <= 12:
            return m, y

    # Token-based scan
    tokens = [t.strip(",._/") for t in re.split(r"[\s\-_/]+", text) if t.strip(",._/")]
    month_val = None
    year_val = None
    for t in tokens:
        tl = t.lower()
        if tl in MONTH_NAME_TO_NUM and month_val is None:
            month_val = MONTH_NAME_TO_NUM[tl]
        elif t.isdigit():
            if len(t) == 4 and year_val is None:
                year_val = int(t)
            elif len(t) == 2 and year_val is None:
                year_val = 2000 + int(t)

    if month_val is not None and year_val is not None:
        return month_val, year_val

    # Date string fallback
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d/%b/%Y", "%b %Y", "%B %Y"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.month, dt.year
        except Exception:
            pass

    return None, None


def get_template_for_billing_month(billing_period_or_consumer) -> str:
    """
    Selects the PDF template strictly according to the bill's Billing Month & Year:
      - Before July 2026 -> existing demo.pdf
      - July 2026 -> existing demo.pdf
      - August 2026 -> DEMONEWPDF.pdf
      - August 2026 and all future months -> DEMONEWPDF.pdf

    The selection uses the actual billing month of each generated bill.
    """
    month_num, year_num = parse_billing_month_year(billing_period_or_consumer)

    if year_num is not None and month_num is not None:
        if (year_num, month_num) < (2026, 8):
            if os.path.exists(CLASSIC_TEMPLATE_PATH):
                return CLASSIC_TEMPLATE_PATH
            return MODERN_TEMPLATE_PATH
        else:
            if os.path.exists(MODERN_TEMPLATE_PATH):
                return MODERN_TEMPLATE_PATH
            return CLASSIC_TEMPLATE_PATH

    if os.path.exists(MODERN_TEMPLATE_PATH):
        return MODERN_TEMPLATE_PATH
    return CLASSIC_TEMPLATE_PATH


@dataclass
class Field:
    key: str
    page: int
    x0: float
    top: float
    bottom: float
    x1: Optional[float] = None
    font: str = "Manrope-Regular"
    size: float = 8.0
    align: str = "left"
    pad: float = 1.5
    bg: tuple = (1.0, 1.0, 1.0)
    label: str = ""
    description: str = ""


@dataclass
class TemplateStructure:
    template_path: str
    template_name: str
    page_count: int
    fields: List[Field]
    fields_by_page: Dict[int, List[Field]]
    fields_by_key: Dict[str, Field]
    layout_type: str = "dynamic"
    chart_info: Dict = field(default_factory=dict)
    has_donut: bool = False
    has_chart: bool = False
    billing_message_box: Optional[Tuple[float, float, float, float]] = None


def _sample_background_color(page_img, x0: float, top: float, x1: float, bottom: float, pad: float = 2.0) -> Tuple[float, float, float]:
    """Sample the true background color from rendered page pixels around the bounding box."""
    if page_img is None:
        return (1.0, 1.0, 1.0)
    w, h = page_img.size
    samples = []
    # Sample above and below the text line to get clear background without text glyphs
    y_above = max(0, min(h - 1, int(top - pad)))
    y_below = max(0, min(h - 1, int(bottom + pad)))
    step = max(1, int(x1 - x0) // 5)
    for x in range(max(0, int(x0)), min(w, int(x1)), step):
        samples.append(page_img.getpixel((x, y_above)))
        samples.append(page_img.getpixel((x, y_below)))

    if not samples:
        return (1.0, 1.0, 1.0)
    
    # Filter out near-black or dark pixels (in case padding touched a border or glyph)
    light_samples = [s for s in samples if sum(s[:3]) > 200]
    target_samples = light_samples if light_samples else samples

    r = sum(s[0] for s in target_samples) / (len(target_samples) * 255.0)
    g = sum(s[1] for s in target_samples) / (len(target_samples) * 255.0)
    b = sum(s[2] for s in target_samples) / (len(target_samples) * 255.0)
    return (round(r, 4), round(g, 4), round(b, 4))


# ----------------------------------------------------------------------
# MASTER TEMPLATE: DEMONEWPDF.pdf (Manrope based)
# ----------------------------------------------------------------------
def _get_new_demo_fields() -> List[Field]:
    # Slate-blue banner background color for "YOUR BILL" section in DEMONEWPDF.pdf
    SLATE_BLUE_BG = (224 / 255, 232 / 255, 245 / 255)
    WHITE_BG = (1.0, 1.0, 1.0)
    MESSAGE_GREY_BG = (224 / 255, 224 / 255, 224 / 255)

    fields = [
        # --- Page 0: Header & Metadata ---
        Field("legacy_no", 0, 230.0, 30.8, 37.8, x1=350.0, pad=0.0, font="Manrope-Bold", size=7.0, label="Distribution Code", bg=WHITE_BG),
        Field("area_label", 0, 230.0, 46.8, 53.8, x1=280.0, pad=0.0, font="Manrope-Bold", size=7.0, label="Area Label", bg=WHITE_BG),
        Field("area", 0, 300.0, 46.8, 53.8, x1=350.0, pad=0.0, font="Manrope-Regular", size=7.0, label="Area", bg=WHITE_BG),
        Field("t_no", 0, 300.0, 58.8, 65.8, x1=350.0, pad=0.0, font="Manrope-Regular", size=7.0, label="T. No.", bg=WHITE_BG),
        Field("billing_mode", 0, 300.0, 70.8, 77.8, x1=350.0, pad=0.0, font="Manrope-Regular", size=7.0, label="Billing mode", bg=WHITE_BG),
        Field("distribution_date", 0, 300.0, 82.8, 89.8, x1=350.0, pad=0.0, font="Manrope-Regular", size=7.0, label="Distribution date", bg=WHITE_BG),

        # --- Page 0: Consumer Details Panel ---
        Field("consumer_name", 0, 40.0, 171.0, 179.0, x1=210.0, font="Manrope-Bold", size=8.0, label="Consumer Name", bg=WHITE_BG),
        Field("address_line1", 0, 40.0, 186.0, 194.0, x1=210.0, font="Manrope-Regular", size=8.0, label="Address Line 1", bg=WHITE_BG),
        Field("address_line2", 0, 40.0, 196.0, 204.0, x1=210.0, font="Manrope-Regular", size=8.0, label="Address Line 2", bg=WHITE_BG),
        Field("address_line3", 0, 40.0, 206.0, 214.0, x1=210.0, font="Manrope-Regular", size=8.0, label="Address Line 3", bg=WHITE_BG),
        Field("address_line4", 0, 40.0, 216.0, 224.0, x1=210.0, font="Manrope-Regular", size=8.0, label="Address Line 4", bg=WHITE_BG),
        Field("address_line5", 0, 40.0, 226.0, 234.0, x1=210.0, font="Manrope-Regular", size=8.0, label="Address Line 5", bg=WHITE_BG),
        Field("mobile_no", 0, 116.4, 246.0, 254.0, x1=210.0, font="Manrope-Bold", size=8.0, label="Registered Mobile", bg=WHITE_BG),
        Field("email", 0, 111.4, 256.0, 264.0, x1=220.0, font="Manrope-Bold", size=8.0, label="Registered Email", bg=WHITE_BG),

        # --- Page 0: Your Details Grid ---
        Field("category", 0, 250.0, 181.0, 189.0, x1=355.0, font="Manrope-Medium", size=8.0, label="CATEGORY", bg=WHITE_BG),
        Field("billing_month", 0, 365.0, 181.0, 189.0, x1=470.0, font="Manrope-Medium", size=8.0, label="BILLING MONTH", bg=WHITE_BG),
        Field("supply_type", 0, 250.0, 212.0, 220.0, x1=355.0, font="Manrope-Medium", size=8.0, label="SUPPLY TYPE", bg=WHITE_BG),
        Field("reading_date", 0, 365.0, 212.0, 220.0, x1=470.0, font="Manrope-Medium", size=8.0, label="READING DATE", bg=WHITE_BG),
        Field("customer_id", 0, 480.0, 213.0, 225.0, x1=565.0, font="Manrope-Bold", size=11.5, label="CUSTOMER ID", bg=WHITE_BG),
        Field("sanctioned_load", 0, 250.0, 243.0, 251.0, x1=355.0, font="Manrope-Medium", size=8.0, label="SANCTIONED LOAD", bg=WHITE_BG),
        Field("bill_date", 0, 365.0, 243.0, 251.0, x1=470.0, font="Manrope-Medium", size=8.0, label="BILL DATE", bg=WHITE_BG),
        Field("substation", 0, 480.0, 243.0, 251.0, x1=585.0, font="Manrope-Medium", size=8.0, label="SUB-STATION", bg=WHITE_BG),

        # --- Page 0: YOUR BILL Block ---
        Field("previous_payment_line", 0, 248.0, 294.0, 319.0, x1=540.0, pad=0.0, font="Manrope-Regular", size=7.5, label="Previous Payment Sentence", bg=SLATE_BLUE_BG),
        Field("headline_due_amount", 0, 30.0, 325.0, 354.0, x1=210.0, pad=0.0, font="Manrope-Bold", size=22.0, label="Total Amount Due", bg=SLATE_BLUE_BG),
        Field("due_by_date", 0, 250.0, 342.5, 352.5, x1=355.0, font="Manrope-Bold", size=10.0, label="DUE BY", bg=SLATE_BLUE_BG),
        Field("security_deposit_held", 0, 372.0, 344.0, 352.0, x1=460.0, font="Manrope-Bold", size=8.0, label="SECURITY DEPOSIT HELD", bg=SLATE_BLUE_BG),
        Field("additional_security", 0, 486.0, 344.0, 352.0, x1=560.0, font="Manrope-Bold", size=8.0, label="ADDITIONAL SECURITY DEPOSIT REQUIRED", bg=SLATE_BLUE_BG),

        # --- Page 0: Meter Details Box ---
        Field("meter_no", 0, 62.0, 419.0, 427.0, x1=115.0, font="Manrope-Regular", size=8.0, label="Meter No.", bg=WHITE_BG),
        Field("present_reading", 0, 85.0, 434.8, 441.8, x1=115.0, font="Manrope-Regular", size=7.0, align="right", label="Present Reading", bg=WHITE_BG),
        Field("past_reading", 0, 85.0, 453.8, 460.8, x1=115.0, font="Manrope-Regular", size=7.0, align="right", label="Previous Reading", bg=WHITE_BG),
        Field("multiplier", 0, 95.0, 468.8, 475.8, x1=115.0, font="Manrope-Regular", size=7.0, align="right", label="Multiplier", bg=WHITE_BG),
        Field("consumption_units", 0, 98.0, 487.8, 494.8, x1=113.0, pad=0.0, font="Manrope-Bold", size=7.0, align="right", label="Consumption", bg=WHITE_BG),
        Field("consumption_sentence_units", 0, 140.0, 517.5, 526.0, x1=185.0, font="Manrope-Regular", size=9.0, label="Net Units Billed", bg=WHITE_BG),

        # --- Page 0: Major Bill Components (Donut) ---
        Field("donut_energy_charges", 0, 518.0, 426.2, 434.2, x1=575.0, font="Manrope-Bold", size=8.0, label="Donut Energy Charges", bg=WHITE_BG),
        Field("donut_fppca_charges", 0, 518.0, 406.2, 414.2, x1=575.0, font="Manrope-Bold", size=8.0, label="Donut FPPAS Charges", bg=WHITE_BG),
        Field("donut_govt_duty", 0, 518.0, 386.2, 394.2, x1=575.0, font="Manrope-Bold", size=8.0, label="Donut Govt Duty", bg=WHITE_BG),
        Field("donut_fixed_charges", 0, 310.0, 493.2, 501.2, x1=370.0, pad=0.5, font="Manrope-Bold", size=8.0, align="right", label="Donut Fixed Charges", bg=WHITE_BG),
        Field("donut_total_charges", 0, 416.0, 448.0, 462.0, x1=474.0, font="Manrope-Bold", size=9.0, align="center", label="Donut Total Charges", bg=WHITE_BG),

        # --- Page 0: RTGS Bank Account Number ---
        Field("bank_account_no", 0, 445.0, 784.8, 791.8, x1=530.0, font="Manrope-Bold", size=7.0, label="Bank Account No.", bg=WHITE_BG),

        # --- Page 1: Bill Details Breakdown ---
        Field("bd_energy_charges", 1, 240.0, 59.8, 66.8, x1=278.0, font="Manrope-Regular", size=7.0, align="right", label="Energy charges (A)", bg=WHITE_BG),
        Field("bd_fixed_charges", 1, 240.0, 77.8, 84.8, x1=278.0, font="Manrope-Regular", size=7.0, align="right", label="Fixed charges (B)", bg=WHITE_BG),
        Field("bd_base_fppas", 1, 240.0, 95.8, 102.8, x1=278.0, font="Manrope-Regular", size=7.0, align="right", label="Base FPPAS (C)", bg=WHITE_BG),
        Field("bd_fppca_charges", 1, 240.0, 112.8, 119.8, x1=278.0, font="Manrope-Regular", size=7.0, align="right", label="FPPAS charges", bg=WHITE_BG),
        Field("bd_total_charges", 1, 240.0, 129.8, 136.8, x1=278.0, font="Manrope-Medium", size=7.0, align="right", label="Total charges w/o duty", bg=WHITE_BG),
        Field("bd_govt_duty", 1, 240.0, 148.8, 155.8, x1=278.0, font="Manrope-Regular", size=7.0, align="right", label="Govt duty", bg=WHITE_BG),
        Field("bd_total_amount_due", 1, 240.0, 165.8, 172.8, x1=278.0, font="Manrope-Medium", size=7.0, align="right", label="Bill amount incl duty", bg=WHITE_BG),
        Field("bd_arrear", 1, 240.0, 182.8, 189.8, x1=278.0, font="Manrope-Regular", size=7.0, align="right", label="Previous dues", bg=WHITE_BG),
        Field("bd_other_debit_credit", 1, 240.0, 200.8, 207.8, x1=278.0, font="Manrope-Regular", size=7.0, align="right", label="Other debit or credit", bg=WHITE_BG),
        Field("bd_delay_surcharge", 1, 240.0, 218.8, 225.8, x1=278.0, font="Manrope-Regular", size=7.0, align="right", label="Delayed payment charges", bg=WHITE_BG),
        Field("bd_net_amount_after_due", 1, 235.0, 234.3, 243.3, x1=278.0, font="Manrope-Medium", size=9.0, align="right", label="Amount due", bg=WHITE_BG),

        # --- Page 1: Important Message Box ---
        Field("billing_message_box", 1, 43.0, 254.0, 350.0, x1=278.0, bg=MESSAGE_GREY_BG, label="Important Message Box"),

        # --- Page 1: Payment Coupon ---
        Field("coupon_group_no", 1, 96.0, 814.0, 823.0, x1=180.0, pad=0.0, font="Manrope-Medium", size=6.0, label="Coupon Group No.", bg=WHITE_BG),
        Field("coupon_customer_id", 1, 250.0, 814.0, 823.0, x1=325.0, pad=0.0, font="Manrope-Medium", size=6.0, label="Coupon Customer ID", bg=WHITE_BG),
        Field("coupon_due_date", 1, 377.0, 814.0, 823.0, x1=450.0, pad=0.0, font="Manrope-Medium", size=6.0, label="Coupon Due Date", bg=WHITE_BG),
        Field("coupon_amount_upto_due", 1, 525.0, 814.0, 823.0, x1=565.0, pad=0.0, font="Manrope-Medium", size=6.0, label="Coupon Bill Amount", bg=WHITE_BG),
    ]
    return fields


# ----------------------------------------------------------------------
# CLASSIC TEMPLATE: demo.pdf (NeurialGrotesk based)
# ----------------------------------------------------------------------
def _get_classic_demo_fields() -> List[Field]:
    CREAM_BG = (247 / 255, 242 / 255, 238 / 255)
    ORANGE_BG = (1.0, 0.54902, 0.0)
    MESSAGE_BG = (0.90980, 0.90588, 0.88235)
    WHITE_BG = (1.0, 1.0, 1.0)

    return [
        Field("area", 0, 275.0, 34.1, 41.1, x1=340, font="NeurialGrotesk-Bold", size=7.0, bg=WHITE_BG),
        Field("t_no", 0, 275.0, 54.1, 61.1, x1=340, size=7.0, bg=WHITE_BG),
        Field("billing_mode", 0, 275.0, 64.1, 71.1, x1=340, size=7.0, bg=WHITE_BG),
        Field("legacy_no", 0, 275.0, 74.1, 81.1, x1=340, size=7.0, bg=WHITE_BG),
        Field("bill_no", 0, 275.0, 94.1, 101.1, x1=340, size=7.0, bg=WHITE_BG),
        Field("consumer_name", 0, 41.8, 163.4, 170.4, x1=195, font="NeurialGrotesk-Bold", size=7.0, bg=WHITE_BG),
        Field("address_line1", 0, 41.8, 172.6, 180.6, x1=195, size=8.0, bg=WHITE_BG),
        Field("address_line2", 0, 41.8, 182.6, 190.6, x1=195, size=8.0, bg=WHITE_BG),
        Field("mobile_no", 0, 126.9, 202.6, 210.6, x1=205, size=8.0, bg=WHITE_BG),
        Field("email", 0, 41.8, 222.6, 230.6, x1=200, size=8.0, bg=WHITE_BG),
        Field("category", 0, 209.2, 172.2, 180.2, x1=300, font="NeurialGrotesk-Regular", size=8.0, bg=WHITE_BG),
        Field("billing_month", 0, 316.6, 172.2, 180.2, x1=430, font="NeurialGrotesk-Regular", size=8.0, bg=WHITE_BG),
        Field("supply_type", 0, 209.2, 207.7, 215.7, x1=300, font="NeurialGrotesk-Regular", size=8.0, bg=WHITE_BG),
        Field("reading_date", 0, 316.6, 207.7, 215.7, x1=430, font="NeurialGrotesk-Regular", size=8.0, bg=WHITE_BG),
        Field("customer_id", 0, 435.4, 207.7, 215.7, x1=543, font="NeurialGrotesk-Bold", size=8.0, bg=WHITE_BG),
        Field("sanctioned_load", 0, 209.2, 244.3, 252.3, x1=300, font="NeurialGrotesk-Regular", size=8.0, bg=WHITE_BG),
        Field("bill_date", 0, 316.6, 244.3, 252.3, x1=430, font="NeurialGrotesk-Regular", size=8.0, bg=WHITE_BG),
        Field("substation", 0, 435.4, 244.3, 252.3, x1=543, font="NeurialGrotesk-Regular", size=8.0, bg=WHITE_BG),
        Field("previous_payment_line", 0, 198.8, 294.3, 303.4, x1=543, size=9.0, bg=ORANGE_BG),
        Field("headline_due_amount", 0, 41.8, 332.3, 356.3, x1=190, font="NeurialGrotesk-Bold", size=24, pad=2.0, bg=ORANGE_BG),
        Field("due_by_date", 0, 198.8, 343.2, 351.2, x1=300, font="NeurialGrotesk-Bold", size=8.0, bg=ORANGE_BG),
        Field("security_deposit_held", 0, 321.5, 345.3, 353.4, x1=430, font="NeurialGrotesk-Regular", size=8.0, pad=0.5, bg=ORANGE_BG),
        Field("additional_security", 0, 439.0, 345.3, 353.4, x1=543, font="NeurialGrotesk-Regular", size=8.0, pad=0.5, bg=ORANGE_BG),
        Field("meter_no", 0, 63.2, 418.5, 425.5, x1=116, pad=1, size=7.0, bg=CREAM_BG),
        Field("present_reading", 0, 80.0, 436.0, 443.0, x1=116, pad=1, size=7.0, align="right", bg=CREAM_BG),
        Field("past_reading", 0, 80.0, 455.0, 462.0, x1=116, pad=1, size=7.0, align="right", bg=CREAM_BG),
        Field("multiplier", 0, 89.0, 470.2, 477.2, x1=116, pad=1, size=7.0, align="right", bg=CREAM_BG),
        Field("consumption_units", 0, 90.0, 488.8, 495.8, x1=116, pad=1, font="NeurialGrotesk-Bold", size=7.0, align="right", bg=CREAM_BG),
        Field("consumption_sentence_units", 0, 107.3, 514.9, 525.1, x1=141, pad=1, font="NeurialGrotesk-Bold", size=9.0, bg=CREAM_BG),
        Field("donut_energy_charges", 0, 341.0, 431.7, 439.8, x1=385.0, pad=0.5, font="NeurialGrotesk-Bold", size=8.0, bg=CREAM_BG),   
        Field("donut_fixed_charges", 0, 519.4, 432.9, 441.0, x1=560, pad=0.5, font="NeurialGrotesk-Bold", size=8.0, bg=CREAM_BG),
        Field("donut_total_charges", 0, 427.3, 448.6, 456.6, x1=468, pad=1, font="NeurialGrotesk-Bold", size=8.0, bg=CREAM_BG),
        Field("donut_fppca_charges", 0, 519.4, 494.9, 503.0, x1=560, pad=0.5, font="NeurialGrotesk-Bold", size=8.0, bg=CREAM_BG),

        # Page 1
        Field("billing_message_box", 1, 43.2, 273.4, 351.67, x1=278.67, bg=MESSAGE_BG),
        Field("bd_fixed_charges", 1, 258.6, 61.3, 68.3, x1=277.2, align="right", size=7.0),
        Field("bd_energy_charges", 1, 257.6, 80.3, 87.3, x1=277.2, align="right", size=7.0),
        Field("bd_fppca_charges", 1, 259.6, 99.3, 106.3, x1=277.2, align="right", size=7.0),
        Field("bd_total_charges", 1, 255.1, 118.3, 125.3, x1=277.2, align="right", font="NeurialGrotesk-Bold", size=7.0),
        Field("bd_arrear", 1, 237.6, 137.3, 144.3, x1=277.2, align="right", size=7.0),
        Field("bd_other_debit_credit", 1, 261.7, 156.3, 163.3, x1=277.2, align="right", size=7.0),
        Field("bd_prompt_rebate", 1, 260.4, 175.3, 182.3, x1=277.2, align="right", size=7.0),
        Field("bd_advance_rebate", 1, 261.7, 194.3, 201.3, x1=277.2, align="right", size=7.0),
        Field("bd_total_amount_due", 1, 254.6, 213.3, 220.3, x1=277.2, align="right", font="NeurialGrotesk-Bold", size=7.0),
        Field("bd_delay_surcharge", 1, 273.2, 232.3, 239.3, x1=277.2, align="right", size=7.0),
        Field("bd_net_amount_after_due", 1, 255.9, 251.3, 258.3, x1=277.2, align="right", font="NeurialGrotesk-Bold", size=7.0),
        Field("coupon_group_no", 1, 44.9, 820.6, 826.6, x1=120.0, pad=0.5, font="NeurialGrotesk-Extrabold", size=6.0, bg=WHITE_BG),
        Field("coupon_customer_id", 1, 134.2, 820.6, 826.6, x1=230.0, pad=0.5, font="NeurialGrotesk-Extrabold", size=6.0, bg=WHITE_BG),
        Field("coupon_due_date", 1, 239.8, 820.6, 826.6, x1=330.0, pad=0.5, font="NeurialGrotesk-Extrabold", size=6.0, bg=WHITE_BG),
        Field("coupon_amount_upto_due", 1, 367.8, 820.6, 826.6, x1=460.0, pad=0.5, font="NeurialGrotesk-Extrabold", size=6.0, bg=WHITE_BG),
        Field("coupon_amount_after_due", 1, 496.2, 820.6, 826.6, x1=550.0, pad=0.5, font="NeurialGrotesk-Extrabold", size=6.0, bg=WHITE_BG),
    ]


# ----------------------------------------------------------------------
# DYNAMIC ARBITRARY PDF TEMPLATE DETECTOR
# ----------------------------------------------------------------------
def _detect_dynamic_template_fields(template_path: str) -> List[Field]:
    """
    Intelligently discover labels and value bounding boxes from an unknown PDF template.
    Extracts text positions, searches for standard billing labels, and finds corresponding values.
    """
    fields = []
    
    LABEL_PATTERNS = [
        ("customer_id", r"customer\s*id", "below", 12.0, "Manrope-Bold", 8.0),
        ("category", r"category", "below", 10.0, "Manrope-Regular", 8.0),
        ("billing_month", r"billing\s*month", "below", 10.0, "Manrope-Regular", 8.0),
        ("supply_type", r"supply\s*type", "below", 10.0, "Manrope-Regular", 8.0),
        ("reading_date", r"reading\s*date", "below", 10.0, "Manrope-Regular", 8.0),
        ("sanctioned_load", r"sanctioned\s*load", "below", 10.0, "Manrope-Regular", 8.0),
        ("bill_date", r"bill\s*date", "below", 10.0, "Manrope-Regular", 8.0),
        ("substation", r"sub[\s\-_]*station", "below", 10.0, "Manrope-Regular", 8.0),
        ("due_by_date", r"due\s*by", "below", 10.0, "Manrope-Bold", 9.0),
        ("meter_no", r"meter\s*no\.?", "below", 10.0, "Manrope-Regular", 7.0),
        ("present_reading", r"present\s*reading", "right", 0.0, "Manrope-Regular", 7.0),
        ("past_reading", r"previous\s*reading|past\s*reading", "right", 0.0, "Manrope-Regular", 7.0),
        ("multiplier", r"multiplier", "right", 0.0, "Manrope-Regular", 7.0),
        ("consumption_units", r"consumption", "right", 0.0, "Manrope-Bold", 7.0),
    ]

    try:
        pdf_doc = pdfium.PdfDocument(template_path)
    except Exception:
        pdf_doc = None

    with pdfplumber.open(template_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            page_img = pdf_doc[page_idx].render(scale=1).to_pil() if pdf_doc and page_idx < len(pdf_doc) else None
            words = page.extract_words(extra_attrs=["fontname", "size"])
            full_text = page.extract_text() or ""

            # Check for standard labels
            for key, pattern, rel_pos, y_offset, default_font, default_sz in LABEL_PATTERNS:
                for w in words:
                    if re.search(pattern, w["text"], re.IGNORECASE):
                        if rel_pos == "below":
                            # Target is under this label
                            x0 = w["x0"]
                            top = w["bottom"] + 2.0
                            bottom = top + default_sz + 1.0
                            x1 = x0 + 100.0
                        else:
                            # Target is to the right
                            x0 = w["x1"] + 10.0
                            top = w["top"]
                            bottom = w["bottom"]
                            x1 = x0 + 60.0

                        bg = _sample_background_color(page_img, x0, top, x1, bottom)
                        fields.append(Field(
                            key=key,
                            page=page_idx,
                            x0=x0,
                            top=top,
                            bottom=bottom,
                            x1=x1,
                            font=default_font,
                            size=default_sz,
                            bg=bg,
                            label=w["text"],
                        ))
                        break

    return fields


def detect_template_structure(template_path: str) -> TemplateStructure:
    """
    Main entry point: Inspects the PDF file and returns a complete TemplateStructure.
    Automatically identifies whether the template matches DEMONEWPDF.pdf, demo.pdf,
    or is a custom newly uploaded template.
    """
    filename = os.path.basename(template_path).lower()
    
    # Read text to identify signature font or keywords
    sample_text = ""
    font_names = set()
    page_count = 1
    with pdfplumber.open(template_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages[:2]:
            text = page.extract_text()
            if text:
                sample_text += " " + text
            chars = page.chars
            for c in chars:
                fn = c.get("fontname")
                if fn:
                    font_names.add(fn)

    # Distinguish modern (DEMONEWPDF.pdf) from classic (demo.pdf):
    # DEMONEWPDF.pdf uniquely contains "bhavnaben", "vasna", "demonew", or HCE-prefixed Manrope fonts.
    is_new_demo = (
        "demonew" in filename or
        "bhavnaben" in sample_text.lower() or
        "non rgp" in sample_text.lower() or
        "vasna" in sample_text.lower() or
        any("Manrope-ExtraBold" in fn or "HCEHPK" in fn for fn in font_names)
    )

    # Classic demo.pdf uniquely features "ramaji", "vanakbara", "diu", or unprefixed NeurialGrotesk fonts.
    is_classic_demo = (
        not is_new_demo and (
            filename == "demo.pdf" or
            "ramaji" in sample_text.lower() or
            "vanakbara" in sample_text.lower() or
            "diu" in sample_text.lower() or
            any(fn.startswith("NeurialGrotesk") for fn in font_names)
        )
    )

    if is_new_demo:
        fields = _get_new_demo_fields()
        layout_type = "modern_manrope"
        chart_info = {
            "axis_y": 678.75,
            "clear_top": 580.0,
            "clear_x0": 315.0,
            "clear_x1": 545.0,
            "bar_x_positions": [
                (318.0, 333.0), (333.0, 348.0),
                (357.0, 372.0), (372.0, 387.0),
                (396.0, 411.0), (411.0, 426.0),
                (435.0, 450.0), (450.0, 465.0),
                (474.0, 489.0), (489.0, 504.0),
                (513.0, 528.0), (528.0, 543.0),
            ],
            "font": "Manrope-Regular",
        }
        has_donut = True
        has_chart = True
        billing_message_box = (43.0, 254.0, 278.0, 350.0)
    elif is_classic_demo:
        fields = _get_classic_demo_fields()
        layout_type = "classic_neurial"
        chart_info = {
            "axis_y": 679.49,
            "clear_top": 590.0,
            "clear_x0": 316.0,
            "clear_x1": 545.0,
            "bar_x_positions": [
                (318.11, 333.11), (333.11, 348.11),
                (357.11, 372.11), (372.11, 387.11),
                (396.11, 411.11), (411.11, 426.11),
                (435.11, 450.11), (450.11, 465.11),
                (474.11, 489.11), (489.11, 504.11),
                (513.11, 528.11), (528.11, 543.11),
            ],
            "font": "NeurialGrotesk-Regular",
        }
        has_donut = True
        has_chart = True
        billing_message_box = (43.2, 273.4, 278.67, 351.67)
    else:
        # Dynamic extraction for custom third-party template
        fields = _detect_dynamic_template_fields(template_path)
        layout_type = "dynamic"
        chart_info = {}
        has_donut = False
        has_chart = False
        billing_message_box = None

    fields_by_page = {}
    fields_by_key = {}
    for f in fields:
        fields_by_page.setdefault(f.page, []).append(f)
        fields_by_key[f.key] = f

    return TemplateStructure(
        template_path=template_path,
        template_name=os.path.basename(template_path),
        page_count=page_count,
        fields=fields,
        fields_by_page=fields_by_page,
        fields_by_key=fields_by_key,
        layout_type=layout_type,
        chart_info=chart_info,
        has_donut=has_donut,
        has_chart=has_chart,
        billing_message_box=billing_message_box,
    )
