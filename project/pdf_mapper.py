from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional


from template_geometry import get_box_edge

MONTH_ABBREV = {
    "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr",
    "may": "May", "june": "Jun", "july": "Jul", "august": "Aug",
    "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec",
}


def _normalize_month_name(raw: str) -> str:
    token = raw.strip().lower()
    if token in MONTH_ABBREV:
        return MONTH_ABBREV[token]
    if len(token) >= 3:
        token = token[:3].title()
        if token in MONTH_ABBREV.values():
            return token
    return ""


def _add_months(reference: date, offset: int) -> date:
    year = reference.year + (reference.month - 1 + offset) // 12
    month = (reference.month - 1 + offset) % 12 + 1
    return date(year, month, 1)


def _parse_billing_month(raw_value):
    if raw_value is None:
        return "", ""
    if isinstance(raw_value, datetime) or isinstance(raw_value, date):
        return raw_value.strftime("%b"), raw_value.strftime("%Y")

    text = str(raw_value).strip()
    if not text:
        return "", ""

    tokens = [token.strip().strip(",.") for token in text.replace("/", " ").replace("-", " ").split() if token.strip()]
    month = ""
    year = ""
    for token in tokens:
        candidate = _normalize_month_name(token)
        if candidate:
            month = candidate
        elif token.isdigit() and len(token) == 4:
            year = token
        elif token.isdigit() and len(token) == 2:
            if not year:
                year = f"20{token}"

    if not month and tokens:
        try:
            month_num = int(tokens[0])
            if 1 <= month_num <= 12:
                month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][(month_num - 1)]
        except ValueError:
            pass

    return month, year


def _build_chart_axis_labels(billing_month_raw, groups: int = 6):
    current_month, current_year = _parse_billing_month(billing_month_raw)
    if not current_month or not current_year:
        return [""] * groups, [""] * (groups * 2), "", ""

    current_date = datetime.strptime(f"01 {current_month} {current_year}", "%d %b %Y").date()
    month_labels = []
    year_labels = []
    for offset in range(-groups + 1, 1):
        month_date = _add_months(current_date, offset)
        month_labels.append(month_date.strftime("%b"))
        year_labels.extend([str(month_date.year - 1), str(month_date.year)])

    return month_labels, year_labels, current_month, current_year


@dataclass
class Field:
    key: str
    page: int
    x0: float
    top: float
    bottom: float
    x1: Optional[float] = None
    font: str = "NeurialGrotesk-Regular"
    size: float = 8.0
    align: str = "left"
    pad: float = 2.0
    bg: tuple = (1, 1, 1)

CREAM_BG = (247 / 255, 242 / 255, 238 / 255)
ORANGE_BG = (1.0, 0.54902, 0.0)
MESSAGE_BG = (0.90980, 0.90588, 0.88235)

import os
_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.pdf")
_METER_BOX_BBOX = (30, 60, 390, 415)
_METER_BOX_ROWS = [
    (418.5, 425.5),
    (436.0, 443.0),
    (455.0, 462.0),
    (470.2, 477.2),
    (488.8, 495.8),
]
try:
    _METER_BOX_X1 = get_box_edge(_TEMPLATE_PATH, 0, _METER_BOX_BBOX, _METER_BOX_ROWS, side="right", inset=1.5) or 116
except Exception as e:
    print("get_box_edge failed, falling back to 116:", e)
    _METER_BOX_X1 = 116

PAGE1_FIELDS = [
    Field("area", 0, 275.0, 34.1, 41.1, x1=340, font="NeurialGrotesk-Bold", size=7.0),
    Field("t_no", 0, 275.0, 54.1, 61.1, x1=340, size=7.0),
    Field("billing_mode", 0, 275.0, 64.1, 71.1, x1=340, size=7.0),
    Field("legacy_no", 0, 275.0, 74.1, 81.1, x1=340, size=7.0),
    Field("bill_no", 0, 275.0, 94.1, 101.1, x1=340, size=7.0),
    Field("consumer_name", 0, 41.8, 163.4, 170.4, x1=195, font="NeurialGrotesk-Bold", size=7.0),
    Field("address_line1", 0, 41.8, 172.6, 180.6, x1=195, size=8.0),
    Field("address_line2", 0, 41.8, 182.6, 190.6, x1=195, size=8.0),
    Field("mobile_no", 0, 126.9, 202.6, 210.6, x1=205, size=8.0),
    Field("email", 0, 41.8, 222.6, 230.6, x1=200, size=8.0),
    Field("category", 0, 209.2, 172.2, 180.2, x1=300, font="NeurialGrotesk-Regular", size=8.0),
    Field("billing_month", 0, 316.6, 172.2, 180.2, x1=430, font="NeurialGrotesk-Regular", size=8.0),
    Field("supply_type", 0, 209.2, 207.7, 215.7, x1=300, font="NeurialGrotesk-Regular", size=8.0),
    Field("reading_date", 0, 316.6, 207.7, 215.7, x1=430, font="NeurialGrotesk-Regular", size=8.0),
    Field("customer_id", 0, 435.4, 207.7, 215.7, x1=543, font="NeurialGrotesk-Bold", size=8.0),
    Field("sanctioned_load", 0, 209.2, 244.3, 252.3, x1=300, font="NeurialGrotesk-Regular", size=8.0),
    Field("bill_date", 0, 316.6, 244.3, 252.3, x1=430, font="NeurialGrotesk-Regular", size=8.0),
    Field("substation", 0, 435.4, 244.3, 252.3, x1=543, font="NeurialGrotesk-Regular", size=8.0),
    Field("previous_payment_line", 0, 198.8, 294.3, 303.4, x1=543, size=9.0, bg=ORANGE_BG),
    Field("headline_due_amount", 0, 53.5, 332.3, 356.3, x1=190, font="NeurialGrotesk-Bold", size=24, pad=2.0, bg=ORANGE_BG),
    Field("due_by_date", 0, 198.8, 343.2, 351.2, x1=300, font="NeurialGrotesk-Bold", size=8.0, bg=ORANGE_BG),
    Field("security_deposit_held", 0, 321.5, 345.3, 353.4, x1=430, font="NeurialGrotesk-Regular", size=8.0, pad=0.5, bg=ORANGE_BG),
    Field("additional_security", 0, 439.0, 345.3, 353.4, x1=543, font="NeurialGrotesk-Regular", size=8.0, pad=0.5, bg=ORANGE_BG),
    Field("meter_no", 0, 63.2, 418.5, 425.5, x1=_METER_BOX_X1, pad=1, size=7.0, bg=CREAM_BG),
    Field("present_reading", 0, 80.0, 436.0, 443.0, x1=_METER_BOX_X1, pad=1, size=7.0, align="right", bg=CREAM_BG),
    Field("past_reading", 0, 80.0, 455.0, 462.0, x1=_METER_BOX_X1, pad=1, size=7.0, align="right", bg=CREAM_BG),
    Field("multiplier", 0, 89.0, 470.2, 477.2, x1=_METER_BOX_X1, pad=1, size=7.0, align="right", bg=CREAM_BG),
    Field("consumption_units", 0, 90.0, 488.8, 495.8, x1=_METER_BOX_X1, pad=1, font="NeurialGrotesk-Bold", size=7.0, align="right", bg=CREAM_BG),
    Field("consumption_sentence_units", 0, 107.3, 514.9, 525.1, x1=141, pad=1,font="NeurialGrotesk-Bold", size=9.0, bg=CREAM_BG),
    Field("chart_year_0", 0, 319.8, 682.49, 687.49, x1=331.41, pad=1.5, font="NeurialGrotesk-Regular", size=5, align="center", bg=CREAM_BG),
    Field("chart_year_1", 0, 334.79, 682.49, 687.49, x1=346.425, pad=1.5, font="NeurialGrotesk-Regular", size=5, align="center", bg=CREAM_BG),
    Field("chart_year_2", 0, 358.8, 682.49, 687.49, x1=370.41, pad=1.5, font="NeurialGrotesk-Regular", size=5, align="center", bg=CREAM_BG),
    Field("chart_year_3", 0, 373.79, 682.49, 687.49, x1=385.425, pad=1.5, font="NeurialGrotesk-Regular", size=5, align="center", bg=CREAM_BG),
    Field("chart_year_4", 0, 397.8, 682.49, 687.49, x1=409.41, pad=1.5, font="NeurialGrotesk-Regular", size=5, align="center", bg=CREAM_BG),
    Field("chart_year_5", 0, 412.79, 682.49, 687.49, x1=424.425, pad=1.5, font="NeurialGrotesk-Regular", size=5, align="center", bg=CREAM_BG),
    Field("chart_year_6", 0, 436.8, 682.49, 687.49, x1=448.41, pad=1.5, font="NeurialGrotesk-Regular", size=5, align="center", bg=CREAM_BG),
    Field("chart_year_7", 0, 451.79, 682.49, 687.49, x1=463.425, pad=1.5, font="NeurialGrotesk-Regular", size=5, align="center", bg=CREAM_BG),
    Field("chart_year_8", 0, 475.79, 682.49, 687.49, x1=487.425, pad=1.5, font="NeurialGrotesk-Regular", size=5, align="center", bg=CREAM_BG),
    Field("chart_year_9", 0, 490.85, 682.49, 687.49, x1=502.375, pad=1.5, font="NeurialGrotesk-Regular", size=5, align="center", bg=CREAM_BG),
    Field("chart_year_10", 0, 514.79, 682.49, 687.49, x1=526.425, pad=1.5, font="NeurialGrotesk-Regular", size=5, align="center", bg=CREAM_BG),
    Field("chart_year_11", 0, 529.85, 682.49, 687.49, x1=541.375, pad=1.5, font="NeurialGrotesk-Regular", size=5, align="center", bg=CREAM_BG),
    Field("chart_month_0", 0, 327.55, 689.802, 695.662, x1=338.66056, pad=1.5, font="NeurialGrotesk-Bold", size=5.86, align="center", bg=CREAM_BG),
    Field("chart_month_1", 0, 367.01, 689.802, 695.662, x1=377.2064, pad=1.5, font="NeurialGrotesk-Bold", size=5.86, align="center", bg=CREAM_BG),
    Field("chart_month_2", 0, 405.46, 689.802, 695.662, x1=416.75808, pad=1.5, font="NeurialGrotesk-Bold", size=5.86, align="center", bg=CREAM_BG),
    Field("chart_month_3", 0, 444.5, 689.802, 695.662, x1=455.72776, pad=1.5, font="NeurialGrotesk-Bold", size=5.86, align="center", bg=CREAM_BG),
    Field("chart_month_4", 0, 483.91, 689.802, 695.662, x1=494.31736, pad=1.5, font="NeurialGrotesk-Bold", size=5.86, align="center", bg=CREAM_BG),
    Field("chart_month_5", 0, 522.75, 689.802, 695.662, x1=533.47966, pad=1.5, font="NeurialGrotesk-Bold", size=5.86, align="center", bg=CREAM_BG),
    Field("donut_energy_charges", 0, 341.0, 431.7, 439.8, x1=385.0, pad=0.5, font="NeurialGrotesk-Bold", size=8.0, bg=CREAM_BG),   
    Field("donut_fixed_charges", 0, 519.4, 432.9, 441.0, x1=560, pad=0.5, font="NeurialGrotesk-Bold", size=8.0, bg=CREAM_BG),
    Field("donut_total_charges", 0, 427.3, 448.6, 456.6, x1=468, pad=1, font="NeurialGrotesk-Bold", size=8.0, bg=CREAM_BG),
    Field("donut_fppca_charges", 0, 519.4, 494.9, 503.0, x1=560, pad=0.5, font="NeurialGrotesk-Bold", size=8.0, bg=CREAM_BG),
]

PAGE2_FIELDS = [
    Field("billing_message_box", 1, 43.2, 273.4, 351.67, x1=278.67, bg=(0.90980, 0.90588, 0.88235)),
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
    Field("coupon_group_no", 1, 44.9, 820.6, 826.6, x1=130, font="NeurialGrotesk-Extrabold", size=6.0),
    Field("coupon_customer_id", 1, 134.2, 820.6, 826.6, x1=235, font="NeurialGrotesk-Extrabold", size=6.0),
    Field("coupon_due_date", 1, 239.8, 820.6, 826.6, x1=340, font="NeurialGrotesk-Extrabold", size=6.0),
    Field("coupon_amount_upto_due", 1, 367.8, 820.6, 826.6, x1=460, font="NeurialGrotesk-Extrabold", size=6.0),
    Field("coupon_amount_after_due", 1, 496.2, 820.6, 826.6, x1=543, font="NeurialGrotesk-Extrabold", size=6.0),
]

ALL_FIELDS = PAGE1_FIELDS + PAGE2_FIELDS


def _format_currency(value: float) -> str:
    return f"{value:,.2f}"


def _format_whole_number(value) -> str:
    if value is None or value == "":
        return ""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if f == int(f):
        return str(int(f))
    return str(f)


_BLANK_TOKENS = {"none", "nan", "null", "n/a", "na"}

def _optional_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in _BLANK_TOKENS else text

def build_field_values(consumer: dict, bill, consumption_history: dict = None) -> dict:
    address = str(consumer.get("address") or "")
    address = " ".join(address.split())
    address_parts = [part.strip() for part in address.split(",") if part.strip()]
    address_line1 = address_parts[0] if len(address_parts) > 0 else address
    address_line2 = ", ".join(address_parts[1:]) if len(address_parts) > 1 else ""

    billing_month_raw = consumer.get("billing_month")
    month_labels, year_labels, current_month, current_year = _build_chart_axis_labels(billing_month_raw, groups=6)
    cust_id = str(consumer.get("customer_id") or "")
    cust_history = (consumption_history or {}).get(cust_id, {})
    chart_values = []
    for i in range(len(month_labels)):
        m = month_labels[i]
        y_prev, y_curr = year_labels[i * 2], year_labels[i * 2 + 1]
        chart_values.append(cust_history.get((m, y_prev)))
        chart_values.append(cust_history.get((m, y_curr)))

    # The last slot is always the current billing month. Its value should
    # never depend on whether the uploaded history sheet happens to
    # already contain a row for this exact month/year - the whole point
    # of this bill is that we already know its consumption authoritatively
    # (bill.units_consumed). Without this, the current month's bar and
    # label silently vanish whenever the sheet doesn't yet have that row,
    # which is the common case (you're generating this bill right now).
    if chart_values:
        chart_values[-1] = bill.units_consumed

    mobile = str(consumer.get("mobile_no") or "")
    masked_mobile = ("*" * max(len(mobile) - 4, 0)) + mobile[-4:] if mobile else ""

    email = str(consumer.get("email") or "")
    masked_email = email
    if "@" in email:
        local, domain = email.split("@", 1)
        if len(local) > 4:
            masked_email = local[:2] + "*" * (len(local) - 4) + local[-2:] + "@" + domain

    previous_payment = consumer.get("previous_payment") or 0
    previous_payment_date = consumer.get("previous_payment_date") or ""

    start_reading_text = _format_whole_number(consumer.get("start_reading"))

    values = {
        "area": str(consumer.get("area") or ""),
        "t_no": str(consumer.get("bill_no") or ""),
        "billing_mode": str(consumer.get("billing_mode") or ""),
        "legacy_no": str(consumer.get("legacy_no") or ""),
        "bill_no": str(consumer.get("bill_no") or ""),
        "consumer_name": " ".join(str(consumer.get("consumer_name") or "").split()).replace(" ,", ",").upper(),
        "address_line1": address_line1.upper(),
        "address_line2": address_line2.upper(),
        "mobile_no": masked_mobile,
        "email": masked_email,
        "category": str(consumer.get("category") or "").upper(),
        "billing_month": str(consumer.get("billing_month") or ""),
        "supply_type": str(consumer.get("supply_type") or ""),
        "reading_date": str(consumer.get("reading_date") or ""),
        "customer_id": str(consumer.get("customer_id") or ""),
        "sanctioned_load": f"{bill.sanctioned_load_kw:.2f} kW",
        "bill_date": str(consumer.get("bill_date") or ""),
        "substation": str(consumer.get("substation") or ""),
        "previous_payment_line": (
            f"Thank you for your previous payment of Rs.{round(float(previous_payment)):,.2f} "
            f"on {previous_payment_date}."
            if previous_payment else ""
        ),
        "headline_due_amount": f"{round(bill.total_amount_due):,.2f}",
        "due_by_date": str(consumer.get("due_date") or ""),
        "security_deposit_held": _format_currency(float(consumer.get('security_deposit') or 0)),
        "additional_security": _format_currency(float(consumer.get('additional_security') or 0)),
        "meter_no": str(consumer.get("meter_no") or ""),
        "present_reading": _format_whole_number(consumer.get("end_reading")),
        "past_reading": f"- {start_reading_text}" if start_reading_text else "",
        "multiplier": f"x {float(consumer.get('multiplier') or 1):.2f}",
        "consumption_units": str(int(bill.units_consumed)),
        "consumption_sentence_units": f"{int(bill.units_consumed)} units",
        "donut_energy_charges": _format_currency(bill.energy_charges),
        "donut_fixed_charges": _format_currency(bill.fixed_charges),
        "donut_total_charges": _format_currency(bill.total_charges),
        "donut_fppca_charges": _format_currency(bill.fppca_charges),
        "bd_fixed_charges": _format_currency(bill.fixed_charges),
        "bd_energy_charges": _format_currency(bill.energy_charges),
        "bd_fppca_charges": _format_currency(bill.fppca_charges),
        "bd_total_charges": _format_currency(bill.total_charges),
        "bd_arrear": _format_currency(bill.arrear),
        "bd_other_debit_credit": _format_currency(bill.other_debit_credit),
        "bd_prompt_rebate": f"-{_format_currency(bill.prompt_rebate)}" if bill.prompt_rebate else "0.00",
        "bd_advance_rebate": f"-{_format_currency(bill.advance_rebate)}" if bill.advance_rebate else "0.00",
        "bd_total_amount_due": _format_currency(bill.total_amount_due),
        "bd_delay_surcharge": _format_currency(bill.delay_surcharge),
        "bd_net_amount_after_due": _format_currency(bill.amount_after_due_date),
        "coupon_group_no": str(consumer.get("group_no") or ""),
        "coupon_customer_id": str(consumer.get("customer_id") or ""),
        "coupon_due_date": str(consumer.get("due_date") or ""),
        "coupon_amount_upto_due": _format_currency(bill.total_amount_due),
        "coupon_amount_after_due": _format_currency(bill.amount_after_due_date),
        "chart_current_value": str(int(bill.units_consumed)),
        "chart_values": chart_values,
      **{f"chart_year_{i}": y for i, y in enumerate(year_labels)},
        **{f"chart_month_{i}": m for i, m in enumerate(month_labels)},
    }
    values["_bill_total_amount_due"] = bill.total_amount_due
    values["_bill_amount_after_due_date"] = bill.amount_after_due_date
    return values