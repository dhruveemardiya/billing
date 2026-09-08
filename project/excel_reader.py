"""
excel_reader.py
================
Reads the uploaded Excel workbook and turns every row into a plain
dictionary of consumer data, ready to be handed to billing_engine.py.

Column names are matched case-insensitively and with underscores/spaces
treated the same way, so slightly different header formatting won't break
the import. Only the *raw* inputs needed for calculation and display are
extracted here - anything pre-calculated in the source spreadsheet (e.g. a
'Total_Amount' column) is intentionally ignored, since billing_engine.py is
the single source of truth for computed values.

FALLBACK / DEFAULT VALUES
--------------------------
Some sheets (e.g. a contact-list style sheet that only has
Name / Address / Email) won't have every billing column. Rather than
generating a bill full of blank boxes and "0.00" everywhere, any column
that's missing from the sheet - or blank for a given row - is filled in
with a sample/default value (DEFAULT_CONSUMER_VALUES below) so the bill
still renders fully populated, the same way it does when you use a
completely-filled sheet like data.xlsx.

Those defaults are NOT hard-coded numbers sitting in this file - they are
read directly out of demo.pdf's own baked-in sample bill, via
demo_defaults.py. If demo.pdf is ever replaced with a different sample
bill, the fallback values used here update automatically.

The 5 identity fields in PROTECTED_BLANK_FIELDS are the exception: those
must come from the real data. If they're missing, they are left blank
instead of being padded with a sample value.
"""

from typing import Dict, List

import openpyxl

from demo_defaults import get_default_consumer_values

# Maps an internal field name -> list of acceptable header aliases found in
# the spreadsheet (case-insensitive, spaces/underscores interchangeable).
COLUMN_ALIASES: Dict[str, List[str]] = {
    "customer_id": ["Customer_ID", "Customer ID", "CustomerID"],
    "consumer_name": ["Consumer_Name", "Consumer Name", "Name"],
    "address": ["Address"],
    "mobile_no": ["Mobile_No", "Mobile No", "Mobile"],
    "email": ["Email", "Email_ID", "Email ID"],
    "category": ["Category"],
    "supply_type": ["Supply_Type", "Supply Type"],
    "sanctioned_load": ["Sanctioned_Load", "Sanctioned Load"],
    "billing_month": ["Billing_Month", "Billing Month"],
    "reading_date": ["Reading_Date", "Reading Date"],
    "bill_date": ["Bill_Date", "Bill Date"],
    "due_date": ["Due_Date", "Due Date"],
    "bill_no": ["Bill_No", "Bill No"],
    "meter_no": ["Meter_No", "Meter No"],
    "start_reading": ["Start_Reading", "Past_Reading", "Start Reading"],
    "end_reading": ["End_Reading", "Present_Reading", "End Reading"],
    "multiplier": ["Multiplier"],
    "units": ["Units", "Consumption"],
    "arrear": ["Arrear"],
    "other_debit_credit": ["Other_Debit_Credit", "Other Debit or Credit", "Other Debit/Credit"],
    "prompt_rebate": ["Prompt_Rebate", "Prompt Payment Rebate"],
    "advance_rebate": ["Advance_Rebate", "Advance Payment Rebate"],
    "previous_payment": ["Previous_Payment", "Previous Payment"],
    "previous_payment_date": ["Previous_Payment_Date", "Previous Payment Date"],
    "security_deposit": ["Security_Deposit", "Security Deposit Held"],
    "additional_security": ["Additional_Security", "Additional Security Deposit"],
    "area": ["Area"],
    "substation": ["Substation", "Sub-Station", "Sub_Station"],
    "legacy_no": ["Legacy_No", "Legacy No"],
    "billing_mode": ["Billing_Mode", "Billing Mode"],
    "group_no": ["Group_No", "Group No"],
}

# These 5 fields must come from the uploaded sheet itself. If a row doesn't
# have them, they stay blank in the generated PDF - they are never padded
# with sample/default data.
PROTECTED_BLANK_FIELDS = {
    "customer_id",
    "consumer_name",
    "email",
    "mobile_no",
    "address",
}

# Fallback value for "units" if it can neither be read from the sheet nor
# computed from start/end reading (used only as an absolute last resort -
# see read_consumers below).
DEFAULT_UNITS = 89

# Sample/default values used to fill in any *other* field that's missing
# from the sheet (either the column doesn't exist, or the cell is blank for
# that row). These are NOT hard-coded here - they're read straight out of
# demo.pdf's own baked-in sample bill (see demo_defaults.py), so if that
# template PDF is ever swapped for a different sample bill, these fallback
# values follow automatically instead of silently going stale.
DEFAULT_CONSUMER_VALUES: Dict[str, object] = get_default_consumer_values()


def _normalize(text: str) -> str:
    return str(text).strip().lower().replace(" ", "_").replace("-", "_")


def _build_header_index(header_row) -> Dict[str, int]:
    """Map normalized header text -> column index for the sheet's header row."""
    normalized_headers = {}
    for idx, cell_value in enumerate(header_row):
        if cell_value is None:
            continue
        normalized_headers[_normalize(cell_value)] = idx
    return normalized_headers


def _find_column_index(header_index: Dict[str, int], internal_field: str):
    for alias in COLUMN_ALIASES.get(internal_field, [internal_field]):
        normalized_alias = _normalize(alias)
        if normalized_alias in header_index:
            return header_index[normalized_alias]
    return None


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _apply_defaults(consumer: Dict) -> None:
    """
    Fill in any missing (non-protected) field on `consumer` with its sample
    default, in place. A field counts as "missing" if the column wasn't in
    the sheet at all, or the cell was blank for this row.
    """
    for field, default_value in DEFAULT_CONSUMER_VALUES.items():
        if field in PROTECTED_BLANK_FIELDS:
            continue
        if _is_blank(consumer.get(field)):
            consumer[field] = default_value


def read_consumers(excel_path: str) -> List[Dict]:
    """
    Read every data row from the first worksheet of the given Excel file
    and return a list of normalized consumer dictionaries.
    """
    workbook = openpyxl.load_workbook(excel_path, data_only=True)
    sheet = workbook.worksheets[0]

    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []

    header_row, *data_rows = rows
    header_index = _build_header_index(header_row)

    column_positions = {
        field: _find_column_index(header_index, field) for field in COLUMN_ALIASES
    }

    consumers = []
    for row in data_rows:
        if row is None or all(cell is None for cell in row):
            continue  # skip fully blank rows

        consumer = {}
        for field, col_idx in column_positions.items():
            consumer[field] = row[col_idx] if col_idx is not None and col_idx < len(row) else None

        # A row with no customer id / name is not usable - skip it.
        # (Checked BEFORE defaults are applied - defaults never touch these
        # two fields anyway, but this keeps the intent explicit.)
        if not consumer.get("customer_id") and not consumer.get("consumer_name"):
            continue

        # Fill in every other missing field with its sample default so the
        # bill still renders fully populated instead of blank/"0.00".
        _apply_defaults(consumer)

        if _is_blank(consumer.get("units")):
            start = consumer.get("start_reading")
            end = consumer.get("end_reading")
            multiplier = consumer.get("multiplier") or 1
            if start is not None and end is not None:
                try:
                    consumer["units"] = (float(end) - float(start)) * float(multiplier)
                except (TypeError, ValueError):
                    consumer["units"] = None

        if _is_blank(consumer.get("units")):
            consumer["units"] = DEFAULT_UNITS

        consumers.append(consumer)

    return consumers


def build_consumption_history(consumers: List[Dict]) -> Dict:
    """
    Group every row's Units by (customer_id, month_abbrev, year) so the
    chart can look up any customer's units for any past billing month -
    since history lives as separate rows in the sheet, not columns.
    """
    from pdf_mapper import _parse_billing_month  # local import avoids circularity
    history = {}
    for row in consumers:
        cust_id = str(row.get("customer_id") or "")
        month, year = _parse_billing_month(row.get("billing_month"))
        if not cust_id or not month or not year:
            continue
        history.setdefault(cust_id, {})[(month, year)] = row.get("units")
    return history