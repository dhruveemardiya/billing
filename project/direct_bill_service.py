"""
direct_bill_service.py
======================
Service layer for the Direct Billing Input workflow on index.html.
Supports both single-month and multi-month billing generation with:
  1. Dynamic monthly consumption variation around a reference target (no identical static units).
  2. Continuous unbroken meter reading sequence (Bill N+1 Start = Bill N End).
  3. Single-source-of-truth calculations via billing_engine.py.
  4. Pre-flight Checks A–J verification on every generated PDF.
  5. Individual PDF preview/download and consolidated ZIP packaging for multi-month batches.
"""

import os
import re
import uuid
import random
import hashlib
from datetime import datetime, date, timedelta
from typing import Tuple, Dict, Any, List

import config
import billing_engine
import pdf_generator
import template_detector
import pdf_mapper
from utils.file_utils import zip_directory

MASTER_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DEMONEWPDF.pdf")
if not os.path.exists(MASTER_TEMPLATE_PATH):
    MASTER_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.pdf")

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

BI_MONTHLY_MONTHS = ["February", "April", "June", "August", "October", "December"]


class DirectBillValidationError(Exception):
    """Raised when form input validation fails."""
    pass


def _parse_month_and_year(month_str: str) -> Tuple[str, int]:
    """Parses text like 'February 2026', 'Feb 2026', '2025-06', '02/2026' into canonical (MonthName, Year)."""
    text = str(month_str or "").strip()
    now_year = datetime.now().year

    # Check for YYYY-MM or YYYY/MM (standard HTML5 <input type="month"> value)
    iso_match = re.search(r"^(\d{4})[\/\-](\d{1,2})$", text)
    if iso_match:
        year = int(iso_match.group(1))
        m_idx = int(iso_match.group(2))
        if 1 <= m_idx <= 12:
            return MONTH_NAMES[m_idx - 1], year

    # Check for digit/digit format MM/YYYY or MM-YYYY
    slash_match = re.search(r"^(\d{1,2})[\/\-](\d{4})$", text)
    if slash_match:
        m_idx = int(slash_match.group(1))
        if 1 <= m_idx <= 12:
            return MONTH_NAMES[m_idx - 1], int(slash_match.group(2))

    # Look for year (4 digits)
    year_match = re.search(r"\b(20\d{2})\b", text)
    year = int(year_match.group(1)) if year_match else now_year

    # Look for month name
    lower_text = text.lower()
    for m in MONTH_NAMES:
        if m.lower() in lower_text or m[:3].lower() in lower_text:
            return m, year

    return "", 0


def resolve_billing_period_sequence(start_month_str: str, end_month_str: str, billing_cycle: str) -> List[Tuple[str, int]]:
    """
    Resolves the chronological sequence of billing periods from start_month to end_month (inclusive).
    Business Rules:
      1. Neither Start nor End can be in the future (beyond current system Year and Month).
      2. If Start == End, exactly 1 billing period is generated.
      3. If Start < End:
         - For Monthly: generates all months after Start Month up to and including End Month.
         - For Bi-Monthly: generates all even cycle months (Feb, Apr, Jun, Aug, Oct, Dec) after Start Month up to and including End Month.
      4. End Month cannot be earlier than Start Month.
    """
    start_m, start_y = _parse_month_and_year(start_month_str)
    if not start_m or not start_y:
        raise DirectBillValidationError(f"Invalid Start Billing Month: '{start_month_str}'.")

    # If end_month not provided, default to single month
    if not end_month_str or not end_month_str.strip():
        end_m, end_y = start_m, start_y
    else:
        end_m, end_y = _parse_month_and_year(end_month_str)
        if not end_m or not end_y:
            raise DirectBillValidationError(f"Invalid End Billing Month: '{end_month_str}'.")

    start_m_idx = MONTH_NAMES.index(start_m) + 1
    end_m_idx = MONTH_NAMES.index(end_m) + 1

    start_dt = date(start_y, start_m_idx, 1)
    end_dt = date(end_y, end_m_idx, 1)

    # Future billing prohibition (Current month is the absolute maximum)
    now = datetime.now()
    current_max_dt = date(now.year, now.month, 1)
    current_month_name = MONTH_NAMES[now.month - 1]

    if start_dt > current_max_dt:
        raise DirectBillValidationError(
            f"Start Billing Month cannot be in the future (maximum allowed is {current_month_name} {now.year})."
        )
    if end_dt > current_max_dt:
        raise DirectBillValidationError(
            f"End Billing Month cannot be in the future (maximum allowed is {current_month_name} {now.year})."
        )

    if end_dt < start_dt:
        raise DirectBillValidationError("End Billing Month cannot be earlier than Start Billing Month.")

    periods = []

    # Multi-Month or Single-Month range (start_dt <= cur_dt <= end_dt)
    if billing_cycle == "Bi-Monthly":
        if start_m not in BI_MONTHLY_MONTHS:
            raise DirectBillValidationError(
                f"Start Month for Bi-Monthly cycle must be one of: {', '.join(BI_MONTHLY_MONTHS)}."
            )
        if end_m not in BI_MONTHLY_MONTHS:
            raise DirectBillValidationError(
                f"End Month for Bi-Monthly cycle must be one of: {', '.join(BI_MONTHLY_MONTHS)}."
            )

        cur_dt = start_dt
        while cur_dt <= end_dt:
            m_name = MONTH_NAMES[cur_dt.month - 1]
            if m_name in BI_MONTHLY_MONTHS:
                periods.append((m_name, cur_dt.year))
            nxt_month = cur_dt.month + 2
            nxt_year = cur_dt.year
            if nxt_month > 12:
                nxt_month -= 12
                nxt_year += 1
            cur_dt = date(nxt_year, nxt_month, 1)

    else:  # Monthly
        cur_dt = start_dt
        while cur_dt <= end_dt:
            m_name = MONTH_NAMES[cur_dt.month - 1]
            periods.append((m_name, cur_dt.year))
            nxt_month = cur_dt.month + 1
            nxt_year = cur_dt.year
            if nxt_month > 12:
                nxt_month = 1
                nxt_year += 1
            cur_dt = date(nxt_year, nxt_month, 1)

    if not periods:
        raise DirectBillValidationError("No valid billing periods could be determined in the selected range.")

    max_periods = getattr(config, "MAX_DIRECT_BILL_PERIODS", None)
    if max_periods and len(periods) > max_periods:
        raise DirectBillValidationError(
            f"Maximum allowed generation range is {max_periods} billing periods per session."
        )

    return periods


def generate_dynamic_monthly_units(reference_units: float, count: int) -> List[int]:
    """
    Generates realistic, randomized monthly consumption values around the reference consumption target.
    Ensures that:
      - Units vary realistically (e.g. between min_pct and max_pct jitter).
      - Consecutive periods never have identical units.
      - Units stay above the safety floor (MINIMUM_DYNAMIC_UNITS).
    """
    min_pct = getattr(config, "DEFAULT_UNIT_VARIATION_PERCENT_MIN", 0.04)
    max_pct = getattr(config, "DEFAULT_UNIT_VARIATION_PERCENT_MAX", 0.11)
    floor = getattr(config, "MINIMUM_DYNAMIC_UNITS", 10)

    generated = []
    prev_val = None

    for _ in range(count):
        # Choose random jitter sign and magnitude
        sign = random.choice([-1, 1])
        jitter = random.uniform(min_pct, max_pct) * sign
        val = int(round(reference_units * (1.0 + jitter)))
        if val < floor:
            val = floor

        # Avoid identical values in consecutive periods
        if prev_val is not None and val == prev_val:
            val += random.choice([-3, -2, -1, 1, 2, 3])
            if val < floor:
                val = floor + 1

        generated.append(val)
        prev_val = val

    return generated


def validate_user_inputs(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates all mandatory and optional fields submitted from the user form.
    Returns cleaned and normalized values.
    """
    if not isinstance(data, dict):
        raise DirectBillValidationError("Invalid payload format. Expected JSON object.")

    # 1. Customer ID
    raw_cust_id = str(data.get("customer_id") or "").strip()
    if not raw_cust_id:
        raise DirectBillValidationError("Customer ID is required.")
    if not re.match(r"^[A-Za-z0-9_-]{3,20}$", raw_cust_id):
        raise DirectBillValidationError("Customer ID must be between 3 and 20 alphanumeric characters.")

    # 2. Consumer Name
    raw_name = str(data.get("consumer_name") or "").strip()
    if not raw_name:
        raise DirectBillValidationError("Consumer Name is required.")
    if len(raw_name) < 2 or len(raw_name) > 100:
        raise DirectBillValidationError("Consumer Name must be between 2 and 100 characters.")

    # 3. Address
    raw_address = str(data.get("address") or "").strip()
    if not raw_address:
        raise DirectBillValidationError("Address is required.")
    if len(raw_address) < 5:
        raise DirectBillValidationError("Please enter a complete address (at least 5 characters).")

    # 4. Mobile Number
    raw_mobile = str(data.get("mobile_no") or "").strip()
    clean_mobile = re.sub(r"[\s\-\(\)\+]", "", raw_mobile)
    if clean_mobile.startswith("91") and len(clean_mobile) == 12:
        clean_mobile = clean_mobile[2:]
    if not re.match(r"^[6-9]\d{9}$", clean_mobile):
        raise DirectBillValidationError("Please enter a valid 10-digit mobile number (starts with 6, 7, 8, or 9).")

    # 5. Email (Optional, but validated if supplied)
    raw_email = str(data.get("email") or "").strip()
    if raw_email:
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", raw_email):
            raise DirectBillValidationError("Please enter a valid email address.")

    # 6. Category
    raw_category = str(data.get("category") or "").strip().title()
    if raw_category not in ["Residential", "Commercial"]:
        raise DirectBillValidationError("Category must be either 'Residential' or 'Commercial'.")

    # 7. Billing Cycle
    billing_cycle = str(data.get("billing_cycle") or "Bi-Monthly").strip()
    if billing_cycle not in ["Monthly", "Bi-Monthly"]:
        billing_cycle = "Bi-Monthly"

    # 8. Start Month & End Month
    raw_start_month = str(data.get("start_month") or data.get("billing_month") or "").strip()
    if not raw_start_month:
        raise DirectBillValidationError("Start Billing Month is required.")

    raw_end_month = str(data.get("end_month") or raw_start_month).strip()

    # Resolve period list
    periods = resolve_billing_period_sequence(raw_start_month, raw_end_month, billing_cycle)

    # 9. Initial Start Reading
    raw_start = data.get("start_reading")
    try:
        start_reading = float(raw_start)
        if start_reading < 0:
            raise ValueError()
    except (TypeError, ValueError):
        raise DirectBillValidationError("Start Reading must be a non-negative number.")

    # 10. Reference Units Consumed
    raw_units = data.get("reference_units") if data.get("reference_units") is not None else data.get("units")
    try:
        reference_units = float(raw_units)
        if reference_units <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        raise DirectBillValidationError("Reference Units Consumed must be a positive number greater than zero.")

    return {
        "customer_id": raw_cust_id,
        "consumer_name": raw_name.upper(),
        "address": raw_address,
        "mobile_no": clean_mobile,
        "email": raw_email.lower(),
        "category": raw_category,
        "billing_cycle": billing_cycle,
        "periods": periods,
        "start_month": f"{periods[0][0]} {periods[0][1]}",
        "end_month": f"{periods[-1][0]} {periods[-1][1]}",
        "start_reading": int(start_reading) if start_reading.is_integer() else start_reading,
        "reference_units": int(reference_units) if reference_units.is_integer() else reference_units,
    }


def get_previous_billing_period(month_name: str, year: int, billing_cycle: str) -> Tuple[str, int]:
    """
    Determines the immediately preceding billing period according to Billing Cycle:
      - Monthly: 1 month prior (e.g. Feb 2026 -> Jan 2026, Jan 2026 -> Dec 2025)
      - Bi-Monthly: 2 months prior (e.g. Apr 2026 -> Feb 2026, Feb 2026 -> Dec 2025)
    """
    month_idx = MONTH_NAMES.index(month_name) + 1
    step = 2 if billing_cycle == "Bi-Monthly" else 1
    prev_m_idx = month_idx - step
    prev_y = year
    if prev_m_idx <= 0:
        prev_m_idx += 12
        prev_y -= 1
    return MONTH_NAMES[prev_m_idx - 1], prev_y


def generate_validated_bill_dates(month_name: str, year: int) -> Dict[str, Any]:
    """
    Generates and strictly validates billing dates for month_name and year:
      - Reading Date: random valid date between 1st and 5th of that same billing month.
      - Bill Date: Reading Date + exactly 8 days (strictly 9th to 13th of the same month).
      - Due Date: random date between 22nd and 27th of that same billing month.
      - Validates Reading Date < Bill Date < Due Date (all within the same month).
    """
    month_idx = MONTH_NAMES.index(month_name) + 1

    for _ in range(20):
        day_reading = random.randint(1, 5)
        reading_dt = date(year, month_idx, day_reading)

        bill_dt = reading_dt + timedelta(days=8)

        day_due = random.randint(22, 27)
        due_dt = date(year, month_idx, day_due)

        if (
            reading_dt.month == month_idx and reading_dt.year == year and
            bill_dt.month == month_idx and bill_dt.year == year and
            due_dt.month == month_idx and due_dt.year == year and
            1 <= reading_dt.day <= 5 and
            bill_dt == reading_dt + timedelta(days=8) and
            22 <= due_dt.day <= 27 and
            reading_dt < bill_dt < due_dt
        ):
            return {
                "reading_date": reading_dt.strftime("%d/%m/%Y"),
                "bill_date": bill_dt.strftime("%d/%m/%Y"),
                "due_date": due_dt.strftime("%d/%m/%Y"),
                "reading_dt": reading_dt,
                "bill_dt": bill_dt,
                "due_dt": due_dt,
            }

    raise DirectBillValidationError(f"Could not generate valid billing dates for {month_name} {year}.")


def generate_payment_date_between(bill_dt: date, due_dt: date) -> str:
    """
    Generates a realistic payment date strictly belonging to the previous billing period,
    after the previous bill's Bill Date and on or before its Due Date.
    """
    min_day = bill_dt.day + 1
    max_day = due_dt.day
    pay_day = random.randint(min_day, max_day)
    pay_dt = date(bill_dt.year, bill_dt.month, pay_day)
    return pay_dt.strftime("%d/%m/%Y")


def validate_bill_before_pdf(
    consumer: Dict[str, Any],
    bill,
    expected_period_name: str,
    expected_year: int,
    expected_prev_month: str,
    expected_prev_year: int,
    prev_bill_dt: date = None,
    prev_due_dt: date = None,
):
    """
    Strict pre-PDF validation verifying all rules from Requirements 1-19:
      - Billing Month = correct selected/generated period
      - Reading Date: 1-5 of Billing Month
      - Bill Date: Reading Date + 8 days
      - Due Date: 22-27 of Billing Month
      - Reading Date < Bill Date < Due Date
      - Previous Payment Amount: > 0 and dynamically calculated
      - Previous Payment Date: belongs to previous billing period, between previous Bill Date and Due Date
      - No hardcoded 2015, 2016, 7420, etc.
    """
    month_idx = MONTH_NAMES.index(expected_period_name) + 1

    # 1. Billing Month
    expected_month_str = f"{expected_period_name} {expected_year}"
    if consumer.get("billing_month") != expected_month_str:
        raise DirectBillValidationError(
            f"Billing month mismatch: expected '{expected_month_str}', got '{consumer.get('billing_month')}'"
        )

    # 2. Reading Date
    r_dt = datetime.strptime(consumer["reading_date"], "%d/%m/%Y").date()
    if not (r_dt.year == expected_year and r_dt.month == month_idx and 1 <= r_dt.day <= 5):
        raise DirectBillValidationError(
            f"Invalid reading date: {consumer['reading_date']} for {expected_month_str}. Must be 1-5 of {expected_month_str}."
        )

    # 3. Bill Date
    b_dt = datetime.strptime(consumer["bill_date"], "%d/%m/%Y").date()
    if b_dt != r_dt + timedelta(days=8):
        raise DirectBillValidationError(
            f"Bill date must be Reading date + 8 days. Got reading={consumer['reading_date']}, bill={consumer['bill_date']}."
        )

    # 4. Due Date
    d_dt = datetime.strptime(consumer["due_date"], "%d/%m/%Y").date()
    if not (d_dt.year == expected_year and d_dt.month == month_idx and 22 <= d_dt.day <= 27):
        raise DirectBillValidationError(
            f"Invalid due date: {consumer['due_date']} for {expected_month_str}. Must be 22-27 of {expected_month_str}."
        )

    # 5. Order
    if not (r_dt < b_dt < d_dt):
        raise DirectBillValidationError("Date ordering violation: Reading < Bill < Due date required.")

    # 6. Previous Payment Date
    prev_p_str = consumer.get("previous_payment_date")
    if not prev_p_str:
        raise DirectBillValidationError("Missing dynamic previous payment date.")
    p_dt = datetime.strptime(prev_p_str, "%d/%m/%Y").date()
    prev_m_idx = MONTH_NAMES.index(expected_prev_month) + 1
    if not (p_dt.year == expected_prev_year and p_dt.month == prev_m_idx):
        raise DirectBillValidationError(
            f"Previous payment date {prev_p_str} does not belong to previous period {expected_prev_month} {expected_prev_year}."
        )
    if prev_bill_dt and p_dt <= prev_bill_dt:
        raise DirectBillValidationError(
            f"Previous payment date {prev_p_str} must be after previous bill date {prev_bill_dt.strftime('%d/%m/%Y')}."
        )
    if prev_due_dt and p_dt > prev_due_dt:
        raise DirectBillValidationError(
            f"Previous payment date {prev_p_str} must be on or before previous due date {prev_due_dt.strftime('%d/%m/%Y')}."
        )

    # 7. Previous Payment Amount
    prev_amt = consumer.get("previous_payment")
    if prev_amt is None or float(prev_amt) <= 0:
        raise DirectBillValidationError(f"Invalid previous payment amount: {prev_amt}")
    if "2015" in prev_p_str or "14/07/26" in prev_p_str:
        raise DirectBillValidationError(f"Forbidden hardcoded payment date detected: {prev_p_str}")


def generate_identifiers(fixed_meter_no: str = None) -> Dict[str, Any]:
    """Generates a unique 10-digit Bill_No and consistent/random utility Meter_No."""
    bill_no = f"3004{random.randint(100000, 999999)}"
    meter_no = fixed_meter_no or f"DND{random.randint(10000, 99999)}"
    return {
        "bill_no": bill_no,
        "meter_no": meter_no,
        "security_deposit": 500.00,
        "additional_security": 0.00,
    }


def build_consumption_history_for_consumer(
    consumer: Dict[str, Any],
    current_units: float,
    batch_records: Dict[Tuple[str, str], float] = None,
    reference_units: float = 700.0,
) -> Dict[str, Dict[Tuple[str, str], float]]:
    """
    Constructs a 6-period consumption history dictionary for the PDF bar chart.
    Ensures that:
      - All billing periods generated in the current batch plot their EXACT generated units.
      - Bi-Monthly cycles only contain even months (no odd months inserted).
      - Preceding periods prior to the batch display realistic historical variation.
    """
    cust_id = str(consumer["customer_id"])
    step = 2 if "60" in str(consumer.get("billing_mode") or "60") else 1

    month_labels, year_labels, cur_m, cur_y = pdf_mapper._build_chart_axis_labels(
        consumer["billing_month"], groups=6, step=step
    )

    history_map = {}
    base_units = max(float(current_units or reference_units or 700.0), 50.0)
    batch_records = batch_records or {}

    for i in range(len(month_labels)):
        m = month_labels[i]
        y_prev, y_curr = year_labels[i * 2], year_labels[i * 2 + 1]

        # Prior year bar (m, y_prev)
        if (m, y_prev) in batch_records:
            val_prev = batch_records[(m, y_prev)]
        else:
            h_prev = int(hashlib.md5(f"{cust_id}_{m}_{y_prev}".encode("utf-8")).hexdigest()[:8], 16)
            factor_prev = 0.85 + (h_prev % 30) / 100.0
            val_prev = round(base_units * factor_prev)
        history_map[(m, y_prev)] = float(val_prev)

        # Current year / cycle bar (m, y_curr)
        if i == len(month_labels) - 1:
            # Current bill's period must match current_units exactly
            history_map[(m, y_curr)] = float(current_units)
        elif (m, y_curr) in batch_records:
            # Match the generated bill in this batch exactly!
            history_map[(m, y_curr)] = float(batch_records[(m, y_curr)])
        else:
            h_curr = int(hashlib.md5(f"{cust_id}_{m}_{y_curr}".encode("utf-8")).hexdigest()[:8], 16)
            factor_curr = 0.90 + (h_curr % 25) / 100.0
            val_curr = round(base_units * factor_curr)
            history_map[(m, y_curr)] = float(val_curr)

    return {cust_id: history_map}


def generate_bill_adjustments(cust_id: str, m_name: str, y_num: int, units: float, sanctioned_load_kw: float, category_key: str) -> Dict[str, float]:
    """
    Generates realistic, deterministic bill adjustments:
    - prompt_rebate: standard prompt payment discount (0.5% of pre-duty charges).
    - arrear: realistic dynamic adjustment (overpayment credit balance like -2.29 or carryover arrear).
    - other_debit_credit: dynamic adjustment (0.00 or small adjustment).
    - advance_rebate: dynamic advance payment rebate (0.00).
    """
    fixed_chg = billing_engine.calculate_fixed_charges(sanctioned_load_kw, category_key)
    energy_chg, _ = billing_engine.calculate_energy_charges(units, category_key)
    fppca_chg = billing_engine.calculate_fppca(fixed_chg, energy_chg)
    pre_duty = fixed_chg + energy_chg + fppca_chg

    h_adj = int(hashlib.md5(f"{cust_id}_{m_name}_{y_num}_adj".encode("utf-8")).hexdigest()[:8], 16)

    # Prompt payment rebate: standard 0.5% discount on pre-duty charges
    prompt_rebate = round(pre_duty * 0.005, 2)
    if prompt_rebate < 0.01:
        prompt_rebate = 0.50

    # Arrear: realistic overpayment credit balance (matching demo.pdf: Credit: -2.29) or minor arrear
    variant = h_adj % 100
    if variant < 70:
        arrear = -round(1.0 + (h_adj % 350) / 100.0, 2)
    elif variant < 85:
        arrear = 0.0
    else:
        arrear = round(5.0 + (h_adj % 1500) / 100.0, 2)

    other_debit_credit = 0.0
    advance_rebate = 0.0

    return {
        "arrear": arrear,
        "other_debit_credit": other_debit_credit,
        "prompt_rebate": prompt_rebate,
        "advance_rebate": advance_rebate,
    }


def process_direct_bill(form_data: Dict[str, Any], template_path: str = None) -> Dict[str, Any]:
    """
    Processes direct billing for a single month or multi-month range:
      1. Validates inputs & resolves billing period sequence.
      2. Generates dynamic units for each month around reference units.
      3. Calculates continuous meter readings: Start[N+1] = End[N].
      4. Fully dynamic dates (Reading: 1-5, Bill: +8 days, Due: 22-27 of same month).
      5. Automatically chains previous payment amount and payment date across billing periods.
      6. Evaluates each bill independently through billing_engine.py.
      7. Dynamic 6-period consumption chart with exact batch units.
      8. Generates PDF for every period, verifying Pre-flight Checks A–J.
      9. Packages multi-month bills into a .zip archive.
    """
    clean = validate_user_inputs(form_data)
    periods = clean["periods"]
    count = len(periods)

    # Generate dynamic consumption values for all periods
    dynamic_units_list = generate_dynamic_monthly_units(clean["reference_units"], count)

    # Build batch units map upfront so chart knows all generated periods in this batch
    batch_records = {}
    for (m_name, y_num), u in zip(periods, dynamic_units_list):
        batch_records[(m_name[:3], str(y_num))] = float(u)

    # Master template cache
    template_cache = {}
    if template_path and os.path.exists(template_path) and os.path.basename(template_path) not in ("DEMONEWPDF.pdf", "demo.pdf"):
        custom_template_path = template_path
    else:
        custom_template_path = None

    # Create session output directory
    job_id = uuid.uuid4().hex[:10]
    output_dir = os.path.join(config.OUTPUT_FOLDER, f"direct_{job_id}")
    os.makedirs(output_dir, exist_ok=True)

    safe_id = re.sub(r"[^\w\-]", "_", clean["customer_id"])
    bills = []

    # Sequence state
    current_start_reading = clean["start_reading"]
    session_meter_no = generate_identifiers()["meter_no"]

    # Calculate previous period identity
    first_m_name, first_y_num = periods[0]
    prev_period_m, prev_period_y = get_previous_billing_period(
        first_m_name, first_y_num, clean["billing_cycle"]
    )
    # Pre-calculate previous bill dates so validator has true reference boundaries
    prev_dates_obj = generate_validated_bill_dates(prev_period_m, prev_period_y)
    prev_bill_dt = datetime.strptime(prev_dates_obj["bill_date"], "%d/%m/%Y").date()
    prev_due_dt = datetime.strptime(prev_dates_obj["due_date"], "%d/%m/%Y").date()
    current_prev_payment_date = generate_payment_date_between(prev_dates_obj["bill_dt"], prev_dates_obj["due_dt"])
    last_bill_dt = prev_dates_obj["bill_dt"]
    last_due_dt = prev_dates_obj["due_dt"]

    # Calculate realistic preceding bill amount using tariff engine
    prev_sim_units = generate_dynamic_monthly_units(clean["reference_units"], 1)[0]
    prev_adj = generate_bill_adjustments(
        clean["customer_id"],
        prev_period_m,
        prev_period_y,
        prev_sim_units,
        5.50,
        billing_engine.resolve_category_key(clean["category"]),
    )
    prev_sim_consumer = {
        "customer_id": clean["customer_id"],
        "consumer_name": clean["consumer_name"],
        "category": clean["category"],
        "billing_mode": "60" if clean["billing_cycle"] == "Bi-Monthly" else "30",
        "billing_month": f"{prev_period_m} {prev_period_y}",
        "units": prev_sim_units,
        "sanctioned_load": "5.50 kW",
        "arrear": prev_adj["arrear"],
        "other_debit_credit": prev_adj["other_debit_credit"],
        "prompt_rebate": prev_adj["prompt_rebate"],
        "advance_rebate": prev_adj["advance_rebate"],
    }
    prev_sim_bill = billing_engine.compute_bill(prev_sim_consumer)
    current_prev_payment_amt = round(prev_sim_bill.total_amount_due, 2)
    expected_prev_m, expected_prev_y = prev_period_m, prev_period_y

    for idx, (m_name, y_num) in enumerate(periods):
        month_idx = MONTH_NAMES.index(m_name) + 1
        period_month_str = f"{m_name} {y_num}"
        period_units = dynamic_units_list[idx]
        period_end_reading = current_start_reading + period_units

        dates = generate_validated_bill_dates(m_name, y_num)
        ids = generate_identifiers(fixed_meter_no=session_meter_no)
        period_adj = generate_bill_adjustments(
            clean["customer_id"],
            m_name,
            y_num,
            period_units,
            5.50,
            billing_engine.resolve_category_key(clean["category"]),
        )

        # Build 6 chronological month groups ending at current bill's month (m_name, y_num)
        chart_groups = []
        c_m, c_y = m_name, y_num
        for _ in range(6):
            chart_groups.append((c_m, c_y))
            c_m, c_y = get_previous_billing_period(c_m, c_y, clean["billing_cycle"])
        chart_groups.reverse()

        chart_m_labels = []
        chart_y_labels = []
        chart_v_list = []
        active_chart_periods = []
        cust_id = clean["customer_id"]

        for p_idx, (gm, gy) in enumerate(chart_groups):
            m_abbr = gm[:3]
            y_curr = str(gy)
            y_prev = str(gy - 1)

            chart_m_labels.append(m_abbr)
            chart_y_labels.extend([y_prev, y_curr])

            # Left bar: Prior year
            if (m_abbr, y_prev) in batch_records:
                val_prev = float(batch_records[(m_abbr, y_prev)])
            else:
                h_prev = int(hashlib.md5(f"{cust_id}_{m_abbr}_{y_prev}".encode("utf-8")).hexdigest()[:8], 16)
                pct_prev = ((h_prev % 21) - 10) / 100.0
                val_prev = float(max(1, round(clean["reference_units"] * (1.0 + pct_prev))))
                batch_records[(m_abbr, y_prev)] = val_prev

            # Right bar: Current cycle
            if p_idx == 5:
                # Current/latest bill is always the rightmost group, using actual generated units
                val_curr = float(period_units)
            elif (m_abbr, y_curr) in batch_records:
                val_curr = float(batch_records[(m_abbr, y_curr)])
            else:
                h_curr = int(hashlib.md5(f"{cust_id}_{m_abbr}_{y_curr}".encode("utf-8")).hexdigest()[:8], 16)
                pct_curr = ((h_curr % 21) - 10) / 100.0
                val_curr = float(max(1, round(clean["reference_units"] * (1.0 + pct_curr))))
                batch_records[(m_abbr, y_curr)] = val_curr

            chart_v_list.append(val_prev)
            chart_v_list.append(val_curr)
            active_chart_periods.append((m_abbr, y_curr, val_curr))

        hl_bar_idx = 11  # Current bill is always the rightmost bar (bar 11)

        consumer = {
            "customer_id": clean["customer_id"],
            "consumer_name": clean["consumer_name"],
            "address": clean["address"],
            "area": "Diu",
            "mobile_no": clean["mobile_no"],
            "email": clean["email"],
            "category": clean["category"],
            "supply_type": "Three Phase",
            "sanctioned_load": "5.50 kW",
            "billing_month": period_month_str,
            "billing_mode": "60" if clean["billing_cycle"] == "Bi-Monthly" else "30",
            "reading_date": dates["reading_date"],
            "bill_date": dates["bill_date"],
            "due_date": dates["due_date"],
            "bill_no": ids["bill_no"],
            "meter_no": ids["meter_no"],
            "start_reading": current_start_reading,
            "end_reading": period_end_reading,
            "multiplier": 1,
            "units": period_units,
            "arrear": period_adj["arrear"],
            "other_debit_credit": period_adj["other_debit_credit"],
            "prompt_rebate": period_adj["prompt_rebate"],
            "advance_rebate": period_adj["advance_rebate"],
            "security_deposit": ids["security_deposit"],
            "additional_security": ids["additional_security"],
            "previous_payment_date": current_prev_payment_date,
            "previous_payment": current_prev_payment_amt,
            "chart_month_labels": chart_m_labels,
            "chart_year_labels": chart_y_labels,
            "chart_values": chart_v_list,
            "highlight_bar_index": hl_bar_idx,
        }

        # Calculate bill independently through single source of truth
        bill = billing_engine.compute_bill(consumer)

        # Build consumption history for chart
        history = {
            clean["customer_id"]: {
                (gm[:3], str(gy)): chart_v_list[2 * k + 1]
                for k, (gm, gy) in enumerate(chart_groups)
            }
        }
        history[clean["customer_id"]].update({
            (gm[:3], str(gy - 1)): chart_v_list[2 * k]
            for k, (gm, gy) in enumerate(chart_groups)
        })

        # Section 23: Required debug logging before generating EVERY PDF
        print("\n-------------------")
        print("GENERATING BILL")
        print(f"Billing Month: {period_month_str}")
        print(f"Reading Date: {consumer['reading_date']}")
        print(f"Bill Date: {consumer['bill_date']}")
        print(f"Due Date: {consumer['due_date']}")
        print("")
        print(f"Start Reading: {consumer['start_reading']}")
        print(f"Units: {consumer['units']}")
        print(f"End Reading: {consumer['end_reading']}")
        print("")
        print(f"Previous Billing Month: {expected_prev_m} {expected_prev_y}")
        print(f"Previous Payment: Rs. {consumer['previous_payment']:,.2f}")
        print(f"Previous Payment Date: {consumer['previous_payment_date']}")
        print("")
        print("Chart Data:")
        for cp in active_chart_periods:
            if cp[0]:
                print(f"{cp[0]} {cp[1]} = {int(cp[2])}")
        print("-------------------\n")

        # Section 24: Required automated assertions before generate_bill_pdf()
        assert consumer["billing_month"] == f"{m_name} {y_num}", f"Billing month mismatch: {consumer['billing_month']} vs {m_name} {y_num}"

        r_dt = datetime.strptime(consumer["reading_date"], "%d/%m/%Y").date()
        b_dt = datetime.strptime(consumer["bill_date"], "%d/%m/%Y").date()
        d_dt = datetime.strptime(consumer["due_date"], "%d/%m/%Y").date()

        assert 1 <= r_dt.day <= 5, f"Reading Date day must be 1-5, got {r_dt.day}"
        assert r_dt.month == month_idx and r_dt.year == y_num, f"Reading Date month/year mismatch: {r_dt} vs {month_idx}/{y_num}"

        assert b_dt == r_dt + timedelta(days=8), f"Bill Date must be Reading Date + 8 days, got {b_dt} vs {r_dt + timedelta(days=8)}"
        assert b_dt.month == month_idx and b_dt.year == y_num, f"Bill Date month/year mismatch: {b_dt} vs {month_idx}/{y_num}"

        assert 22 <= d_dt.day <= 27, f"Due Date day must be 22-27, got {d_dt.day}"
        assert d_dt.month == month_idx and d_dt.year == y_num, f"Due Date month/year mismatch: {d_dt} vs {month_idx}/{y_num}"

        assert r_dt < b_dt < d_dt, f"Date ordering violation: {r_dt} < {b_dt} < {d_dt}"

        assert consumer["end_reading"] == consumer["start_reading"] + consumer["units"], (
            f"End reading mismatch: {consumer['end_reading']} != {consumer['start_reading']} + {consumer['units']}"
        )

        p_dt = datetime.strptime(consumer["previous_payment_date"], "%d/%m/%Y").date()
        prev_m_idx = MONTH_NAMES.index(expected_prev_m) + 1
        assert p_dt.month == prev_m_idx and p_dt.year == expected_prev_y, (
            f"Previous Payment Date {p_dt} does not belong to {expected_prev_m} {expected_prev_y}"
        )
        if last_bill_dt and p_dt <= last_bill_dt:
            raise AssertionError(f"Previous payment date {consumer['previous_payment_date']} must be after previous bill date {last_bill_dt}")
        if last_due_dt and p_dt > last_due_dt:
            raise AssertionError(f"Previous payment date {consumer['previous_payment_date']} must be on or before previous due date {last_due_dt}")

        if idx > 0:
            assert round(consumer["previous_payment"], 2) == round(bills[idx - 1]["summary"]["total_amount"], 2), (
                f"Previous payment chain mismatch: {consumer['previous_payment']} != {bills[idx - 1]['summary']['total_amount']}"
            )

        for cp in active_chart_periods:
            if cp[0]:
                assert batch_records.get((cp[0], cp[1])) == cp[2], f"Chart value mismatch for {cp[0]} {cp[1]}: {cp[2]}"

        safe_month = period_month_str.replace(" ", "_")
        pad_width = max(2, len(str(count)))
        filename = f"{idx:0{pad_width}d}_Electricity_Bill_{safe_month}_{safe_id}.pdf"
        output_path = os.path.join(output_dir, filename)

        # Select PDF template strictly according to this bill's Billing Month & Year:
        # Before July 2026 -> demo.pdf, July 2026 -> demo.pdf, August 2026 and future -> DEMONEWPDF.pdf
        if custom_template_path:
            bill_template = custom_template_path
        else:
            bill_template = template_detector.get_template_for_billing_month(period_month_str)

        if bill_template not in template_cache:
            template_cache[bill_template] = template_detector.detect_template_structure(bill_template)
        bill_ts = template_cache[bill_template]

        # Generate single bill PDF (verifies Checks A–J)
        pdf_generator.generate_bill_pdf(
            template_path=bill_template,
            consumer=consumer,
            bill=bill,
            output_path=output_path,
            consumption_history=history,
            template_structure=bill_ts,
        )

        bill_summary = {
            "index": idx,
            "filename": filename,
            "output_path": output_path,
            "template_used": os.path.basename(bill_template),
            "preview_url": f"/api/preview-bill/{job_id}?filename={filename}&index={idx}",
            "download_url": f"/api/download-bill/{job_id}?filename={filename}&index={idx}",
            "consumer": consumer,
            "summary": {
                "customer_id": clean["customer_id"],
                "consumer_name": clean["consumer_name"],
                "category": clean["category"],
                "billing_month": period_month_str,
                "units": bill.units_consumed,
                "start_reading": consumer["start_reading"],
                "end_reading": consumer["end_reading"],
                "bill_no": consumer["bill_no"],
                "meter_no": consumer["meter_no"],
                "reading_date": consumer["reading_date"],
                "bill_date": consumer["bill_date"],
                "due_date": consumer["due_date"],
                "previous_payment": consumer["previous_payment"],
                "previous_payment_date": consumer["previous_payment_date"],
                "fixed_charges": bill.fixed_charges,
                "energy_charges": bill.energy_charges,
                "fppca_charges": bill.fppca_charges,
                "govt_duty": bill.govt_duty,
                "total_amount": bill.total_amount_due,
                "delayed_payment_charges": bill.delay_surcharge,
                "amount_after_due": bill.amount_after_due_date,
            }
        }
        bills.append(bill_summary)

        # Continuous meter sequence & previous payment chain for NEXT bill
        current_start_reading = period_end_reading
        current_prev_payment_amt = round(bill.total_amount_due, 2)
        current_prev_payment_date = generate_payment_date_between(dates["bill_dt"], dates["due_dt"])
        expected_prev_m, expected_prev_y = m_name, y_num
        last_bill_dt = dates["bill_dt"]
        last_due_dt = dates["due_dt"]

    # If multiple bills generated, build consolidated ZIP archive
    zip_download_url = None
    zip_filename = None
    if count > 1:
        safe_start = clean["start_month"].replace(" ", "_")
        safe_end = clean["end_month"].replace(" ", "_")
        zip_filename = f"Electricity_Bills_{safe_start}_to_{safe_end}_{safe_id}.zip"
        zip_path = os.path.join(config.OUTPUT_FOLDER, f"{job_id}.zip")
        zip_directory(output_dir, zip_path)
        zip_download_url = f"/api/download-direct-batch-zip/{job_id}"

    primary_bill = bills[0]
    return {
        "success": True,
        "message": f"Successfully generated {count} bill(s).",
        "batch_id": job_id,
        "bill_id": job_id,
        "total_bills": count,
        "is_multi": count > 1,
        "zip_download_url": zip_download_url,
        "zip_filename": zip_filename,
        "bills": bills,
        # Default single-bill convenience shortcuts
        "filename": primary_bill["filename"],
        "download_url": primary_bill["download_url"],
        "preview_url": primary_bill["preview_url"],
        "summary": primary_bill["summary"],
    }
