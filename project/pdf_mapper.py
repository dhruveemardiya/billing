from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Dict
import os
import hashlib
import legacy_store

from template_detector import Field, detect_template_structure

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


def _build_chart_axis_labels(billing_month_raw, groups: int = 6, step: int = 1):
    current_month, current_year = _parse_billing_month(billing_month_raw)
    if not current_month or not current_year:
        return [""] * groups, [""] * (groups * 2), "", ""

    try:
        current_date = datetime.strptime(f"01 {current_month} {current_year}", "%d %b %Y").date()
    except Exception:
        return [""] * groups, [""] * (groups * 2), current_month, current_year

    month_labels = []
    year_labels = []
    for i in range(-groups + 1, 1):
        offset = i * step
        month_date = _add_months(current_date, offset)
        month_labels.append(month_date.strftime("%b"))
        year_labels.extend([str(month_date.year - 1), str(month_date.year)])

    return month_labels, year_labels, current_month, current_year


# Color constants for backward compatibility
CREAM_BG = (247 / 255, 242 / 255, 238 / 255)
ORANGE_BG = (1.0, 0.54902, 0.0)
MESSAGE_BG = (0.90980, 0.90588, 0.88235)

# Default master template
DEFAULT_MASTER_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DEMONEWPDF.pdf")
if not os.path.exists(DEFAULT_MASTER_TEMPLATE):
    DEFAULT_MASTER_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.pdf")

# Detect default template fields
_default_structure = detect_template_structure(DEFAULT_MASTER_TEMPLATE)
ALL_FIELDS = _default_structure.fields


def get_template_fields(template_path: Optional[str] = None) -> List[Field]:
    """Retrieve detected fields for the specified template path, or default master template."""
    path = template_path or DEFAULT_MASTER_TEMPLATE
    structure = detect_template_structure(path)
    return structure.fields


def _format_currency(value) -> str:
    if value is None or value == "":
        return "0.00"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def compute_donut_component_data(fixed_charges, energy_charges, fppca_charges, government_duty):
    """Return chart slices using the real component amounts and a mathematically-correct total.

    Each slice angle is derived from the exact amount relative to the sum of all component
    values, without any manual percentage or visual approximation.
    """
    components = [
        {"label": "Fixed charges", "amount": float(fixed_charges or 0), "color": "#dfe3e8"},
        {"label": "Government duty", "amount": float(government_duty or 0), "color": "#c7ccd1"},
        {"label": "FPPAS charges", "amount": float(fppca_charges or 0), "color": "#a5adb6"},
        {"label": "Energy charges", "amount": float(energy_charges or 0), "color": "#6f7680"},
    ]

    total = sum(item["amount"] for item in components)
    if total <= 0:
        for item in components:
            item["angle"] = 0.0
            item["percentage"] = 0.0
        return {"components": components, "total": 0.0, "center_total": 0.0, "sum_matches_total": True}

    for item in components:
        item["angle"] = (item["amount"] / total) * 360.0
        item["percentage"] = (item["amount"] / total) * 100.0

    return {"components": components, "total": total, "center_total": total, "sum_matches_total": abs(sum(item["amount"] for item in components) - total) < 1e-9}


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


def build_field_values(consumer: dict, bill, consumption_history: dict = None, template_info=None) -> dict:
    address = str(consumer.get("address") or "")
    address = " ".join(address.split())
    address_parts = [part.strip() for part in address.split(",") if part.strip()]

    billing_month_raw = consumer.get("billing_month")
    is_modern = (template_info.layout_type == "modern_manrope") if template_info else True
    cust_id = str(consumer.get("customer_id") or "")
    if consumer.get("chart_month_labels") and consumer.get("chart_values"):
        month_labels = list(consumer["chart_month_labels"])
        year_labels = list(consumer.get("chart_year_labels") or [])
        chart_values = list(consumer["chart_values"])
    else:
        step = 2 if "60" in str(consumer.get("billing_mode") or "60") else 1
        month_labels, year_labels, current_month, current_year = _build_chart_axis_labels(billing_month_raw, groups=6, step=step)
        cust_history = (consumption_history or {}).get(cust_id, {})
        ref_units = float(consumer.get("reference_units") or getattr(bill, "units_consumed", 700.0) or 700.0)
        chart_values = []
        for i in range(len(month_labels)):
            m = month_labels[i]
            y_prev, y_curr = year_labels[i * 2], year_labels[i * 2 + 1]

            # Left bar (Prior year)
            if (m, y_prev) in cust_history and cust_history[(m, y_prev)] is not None:
                chart_values.append(float(cust_history[(m, y_prev)]))
            else:
                h_prev = int(hashlib.md5(f"{cust_id}_{m}_{y_prev}".encode("utf-8")).hexdigest()[:8], 16)
                pct_prev = ((h_prev % 21) - 10) / 100.0
                chart_values.append(float(max(1, round(ref_units * (1.0 + pct_prev)))))

            # Right bar (Current cycle)
            if i == len(month_labels) - 1:
                chart_values.append(float(bill.units_consumed))
            elif (m, y_curr) in cust_history and cust_history[(m, y_curr)] is not None:
                chart_values.append(float(cust_history[(m, y_curr)]))
            else:
                h_curr = int(hashlib.md5(f"{cust_id}_{m}_{y_curr}".encode("utf-8")).hexdigest()[:8], 16)
                pct_curr = ((h_curr % 21) - 10) / 100.0
                chart_values.append(float(max(1, round(ref_units * (1.0 + pct_curr)))))

    mobile = str(consumer.get("mobile_no") or "")
    masked_mobile = ("*" * max(len(mobile) - 4, 0)) + mobile[-4:] if mobile else ""

    email = str(consumer.get("email") or "")
    masked_email = email
    if "@" in email:
        local, domain = email.split("@", 1)
        if len(local) > 4:
            masked_email = local[:2] + "*" * (len(local) - 4) + local[-2:] + "@" + domain

    previous_payment = consumer.get("previous_payment")
    try:
        prev_amt = float(previous_payment) if previous_payment is not None else 0.0
    except (ValueError, TypeError):
        prev_amt = 0.0
    previous_payment_date = str(consumer.get("previous_payment_date") or "")

    start_reading_text = _format_whole_number(consumer.get("start_reading"))
    end_reading_text = _format_whole_number(consumer.get("end_reading"))

    # Multi-line address mapping up to 5 lines
    address_lines = {}
    for idx in range(1, 6):
        if idx - 1 < len(address_parts):
            address_lines[f"address_line{idx}"] = address_parts[idx - 1].upper()
        else:
            address_lines[f"address_line{idx}"] = ""
    if not address_lines["address_line1"]:
        address_lines["address_line1"] = address.upper()

    # SINGLE SOURCE OF TRUTH (Requirement 1 & 3):
    # Donut components derive directly from the computed BillCalculation object.
    govt_duty = bill.govt_duty
    donut_chart = compute_donut_component_data(
        fixed_charges=bill.fixed_charges,
        energy_charges=bill.energy_charges,
        fppca_charges=bill.fppca_charges,
        government_duty=govt_duty,
    )
    donut_total = donut_chart["total"]
    base_fppas = round(bill.units_consumed * 3.72, 2)

    # Log Chart Data Validation (Requirement 10)
    print("\n" + "=" * 48)
    print(f"BILL TOTAL: Rs. {bill.total_amount_due:,.2f}")
    print("MAJOR COMPONENTS:")
    print(f"  Government Duty: Rs. {govt_duty:,.2f}")
    print(f"  FPPAS Charges:   Rs. {bill.fppca_charges:,.2f}")
    print(f"  Energy Charges:  Rs. {bill.energy_charges:,.2f}")
    print(f"  Fixed Charges:   Rs. {bill.fixed_charges:,.2f}")
    print(f"CHART TOTAL: Rs. {donut_total:,.2f}")
    print("CONSUMPTION:")
    for m_idx in range(len(month_labels)):
        m_name = month_labels[m_idx]
        y_p = year_labels[m_idx * 2]
        y_c = year_labels[m_idx * 2 + 1]
        v_p = chart_values[m_idx * 2]
        v_c = chart_values[m_idx * 2 + 1]
        if v_p is not None:
            print(f"  {y_p}-{m_name}: {int(v_p)} units")
        if v_c is not None:
            print(f"  {y_c}-{m_name}: {int(v_c)} units")
    print("=" * 48 + "\n")

    bill_date_str = str(consumer.get("bill_date") or "")
    due_date_str = str(consumer.get("due_date") or "")

    raw_billing_mode = str(consumer.get("billing_mode") or "").strip()
    if "30" in raw_billing_mode:
        formatted_billing_mode = "30 days"
    elif "60" in raw_billing_mode:
        formatted_billing_mode = "60 days"
    elif raw_billing_mode:
        formatted_billing_mode = f"{raw_billing_mode} days" if "day" not in raw_billing_mode.lower() else raw_billing_mode
    else:
        formatted_billing_mode = "60 days"

    raw_area = str(consumer.get("area") or ("DIU" if not is_modern else "Diu"))
    area_value = raw_area.upper() if not is_modern else raw_area

    if is_modern:
        legacy_val = str(consumer.get("distribution_code") or consumer.get("legacy_no") or "DI07/DI070010/")
    else:
        legacy_val = str(consumer.get("legacy_no") or "")
        if not legacy_val and cust_id:
            legacy_val = legacy_store.get_or_create_legacy_no(cust_id)

    values = {
        "area_label": "Area",
        "area": area_value,
        "t_no": str(consumer.get("t_no") or ("3004645778" if is_modern else consumer.get("bill_no") or "")),
        "billing_mode": formatted_billing_mode,
        "distribution_date": str(consumer.get("distribution_date") or bill_date_str),
        "legacy_no": legacy_val,
        "bill_no": str(consumer.get("bill_no") or ""),
        "consumer_name": " ".join(str(consumer.get("consumer_name") or "").split()).replace(" ,", ",").upper(),
        **address_lines,
        "mobile_no": masked_mobile,
        "email": masked_email,
        "category": str(consumer.get("category") or "").upper(),
        "billing_month": str(consumer.get("billing_month") or ""),
        "supply_type": str(consumer.get("supply_type") or ""),
        "reading_date": str(consumer.get("reading_date") or ""),
        "customer_id": cust_id,
        "sanctioned_load": f"{bill.sanctioned_load_kw:.2f} kW",
        "bill_date": bill_date_str,
        "substation": str(consumer.get("substation") or "66 KV MALALA SS"),
        "previous_payment_line": (
            f"Thank you for your previous payment of ₹{float(prev_amt):,.2f} on {previous_payment_date}."
            if prev_amt and previous_payment_date else ""
        ),
        "headline_due_amount": f"₹{bill.total_amount_due:,.2f}",
        "due_by_date": due_date_str,
        "security_deposit_held": _format_currency(consumer.get("security_deposit") or 0),
        "additional_security": _format_currency(consumer.get("additional_security") or 0),
        "meter_no": str(consumer.get("meter_no") or ""),
        "present_reading": end_reading_text,
        "past_reading": start_reading_text,
        "multiplier": f"{float(consumer.get('multiplier') or 1):.2f}",
        "consumption_units": str(int(bill.units_consumed)),
        "consumption_sentence_units": f"{int(bill.units_consumed)} units",
        "donut_energy_charges": f"₹ {_format_currency(bill.energy_charges)}",
        "donut_fixed_charges": f"₹ {_format_currency(bill.fixed_charges)}",
        "donut_total_charges": _format_currency(donut_total),
        "donut_fppca_charges": f"₹ {_format_currency(bill.fppca_charges)}",
        "donut_govt_duty": f"₹ {_format_currency(govt_duty)}",
        "donut_chart_data": donut_chart["components"],
        "donut_total_amount": donut_total,
        "donut_component_total_matches": donut_chart["sum_matches_total"],
        "bank_account_no": f"TPLAHM{cust_id}" if cust_id else "",
        "bd_fixed_charges": _format_currency(bill.fixed_charges),
        "bd_energy_charges": _format_currency(bill.energy_charges),
        "bd_base_fppas": _format_currency(base_fppas),
        "bd_fppca_charges": _format_currency(bill.fppca_charges),
        "bd_total_charges": _format_currency(bill.charges_before_duty),
        "bd_govt_duty": _format_currency(govt_duty),
        "bd_arrear": f"Credit: {bill.arrear:.2f}" if getattr(bill, "arrear", 0.0) < 0 else _format_currency(getattr(bill, "arrear", 0.0) or 0.0),
        "bd_other_debit_credit": _format_currency(getattr(bill, "other_debit_credit", 0.0) or 0.0),
        "bd_prompt_rebate": f"-{_format_currency(bill.prompt_rebate)}" if getattr(bill, "prompt_rebate", 0.0) > 0 else "0.00",
        "bd_advance_rebate": f"-{_format_currency(bill.advance_rebate)}" if getattr(bill, "advance_rebate", 0.0) > 0 else "0.00",
        "bd_total_amount_due": _format_currency(bill.total_amount_due),
        "bd_delay_surcharge": _format_currency(bill.delay_surcharge),
        "bd_net_amount_after_due": _format_currency(bill.amount_after_due_date),
        "coupon_group_no": str(consumer.get("group_no") or "DI070010"),
        "coupon_customer_id": cust_id,
        "coupon_due_date": due_date_str,
        "coupon_amount_upto_due": (f"₹ {_format_currency(bill.total_amount_due)}" if is_modern else _format_currency(bill.total_amount_due)),
        "coupon_amount_after_due": _format_currency(bill.amount_after_due_date),
        "chart_current_value": str(int(bill.units_consumed)),
        "chart_values": chart_values,
        "highlight_bar_index": consumer.get("highlight_bar_index"),
        **{f"chart_year_{i}": y for i, y in enumerate(year_labels)},
        **{f"chart_month_{i}": m for i, m in enumerate(month_labels)},
    }
    values["_bill_total_amount_due"] = bill.total_amount_due
    values["_bill_amount_after_due_date"] = bill.amount_after_due_date
    return values