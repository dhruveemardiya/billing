"""
mapping_engine.py
=================
Maps columns from an uploaded Excel file to detected PDF variables/fields.
Detects mapped fields, computed fields, unmapped Excel columns, and unmapped
PDF variables, producing structured warnings and mapping reports.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import openpyxl

from template_detector import TemplateStructure, Field

# Maps internal field key -> list of acceptable column aliases in Excel
COLUMN_ALIASES: Dict[str, List[str]] = {
    "customer_id": ["customer_id", "customer id", "customerid", "consumer_no", "account_no", "service_no", "cid"],
    "coupon_customer_id": ["customer_id", "customer id", "customerid", "consumer_no"],
    "bank_account_no": ["customer_id", "customer id", "account_no"],
    "consumer_name": ["consumer_name", "consumer name", "customer_name", "customer name", "name", "client_name"],
    "address": ["address", "consumer_address", "customer_address", "location"],
    "address_line1": ["address", "consumer_address", "customer_address"],
    "address_line2": ["address"],
    "address_line3": ["address"],
    "mobile_no": ["mobile_no", "mobile no", "mobile", "phone_no", "phone", "contact_no", "cell"],
    "email": ["email", "email_id", "email id", "mail"],
    "category": ["category", "tariff_category", "tariff", "consumer_category"],
    "supply_type": ["supply_type", "supply type", "phase", "connection_type"],
    "sanctioned_load": ["sanctioned_load", "sanctioned load", "connected_load", "load", "contract_load"],
    "billing_month": ["billing_month", "billing month", "bill_month", "month"],
    "reading_date": ["reading_date", "reading date", "meter_reading_date"],
    "bill_date": ["bill_date", "bill date", "invoice_date"],
    "distribution_date": ["distribution_date", "distribution date", "bill_date", "bill date"],
    "due_date": ["due_date", "due date", "due_by", "due by", "payment_due_date"],
    "due_by_date": ["due_date", "due date", "due_by", "due by", "payment_due_date"],
    "coupon_due_date": ["due_date", "due date", "due_by"],
    "bill_no": ["bill_no", "bill no", "invoice_no", "bill_number", "t_no", "t. no."],
    "t_no": ["t_no", "t. no.", "t no", "bill_no", "bill no"],
    "meter_no": ["meter_no", "meter no", "meter_number", "meter_id"],
    "start_reading": ["start_reading", "start reading", "past_reading", "past reading", "previous_reading"],
    "past_reading": ["start_reading", "start reading", "past_reading", "past reading", "previous_reading"],
    "end_reading": ["end_reading", "end reading", "present_reading", "present reading", "current_reading"],
    "present_reading": ["end_reading", "end reading", "present_reading", "present reading", "current_reading"],
    "multiplier": ["multiplier", "meter_multiplier"],
    "units": ["units", "consumption", "units_billed", "net_units", "consumed_units"],
    "consumption_units": ["units", "consumption", "units_billed", "net_units"],
    "consumption_sentence_units": ["units", "consumption", "units_billed"],
    "arrear": ["arrear", "arrears", "previous_dues", "past_dues"],
    "bd_arrear": ["arrear", "arrears", "previous_dues", "past_dues"],
    "other_debit_credit": ["other_debit_credit", "other debit or credit", "other_charges", "debit_credit"],
    "bd_other_debit_credit": ["other_debit_credit", "other debit or credit"],
    "prompt_rebate": ["prompt_rebate", "prompt payment rebate", "prompt_discount"],
    "bd_prompt_rebate": ["prompt_rebate", "prompt payment rebate"],
    "advance_rebate": ["advance_rebate", "advance payment rebate", "advance_discount"],
    "bd_advance_rebate": ["advance_rebate", "advance payment rebate"],
    "govt_duty": ["govt_duty", "govt duty", "government_duty", "government duty", "govt_duty_charges", "govt duty charges", "duty_charges"],
    "bd_govt_duty": ["govt_duty", "govt duty", "government_duty", "government duty", "govt_duty_charges", "govt duty charges", "duty_charges"],
    "delay_surcharge": ["delay_surcharge", "delay surcharge", "delayed_payment_charges", "delayed payment charges", "late_payment_charges", "late payment charges"],
    "bd_delay_surcharge": ["delay_surcharge", "delay surcharge", "delayed_payment_charges", "delayed payment charges", "late_payment_charges", "late payment charges"],
    "previous_payment": ["previous_payment", "previous payment", "last_payment"],
    "previous_payment_date": ["previous_payment_date", "previous payment date", "last_payment_date"],
    "previous_payment_line": ["previous_payment", "previous payment"],
    "security_deposit": ["security_deposit", "security deposit", "security_deposit_held", "deposit"],
    "security_deposit_held": ["security_deposit", "security deposit", "security_deposit_held", "deposit"],
    "additional_security": ["additional_security", "additional security", "additional_security_deposit"],
    "area": ["area", "zone", "division", "circle"],
    "substation": ["substation", "sub-station", "sub_station", "ss"],
    "legacy_no": ["legacy_no", "legacy no", "distribution_code", "legacy_number"],
    "billing_mode": ["billing_mode", "billing mode", "mode"],
    "group_no": ["group_no", "group no", "group_number", "group"],
    "coupon_group_no": ["group_no", "group no", "group_number"],
    "headline_due_amount": ["total_amount", "total amount", "amount_due", "amount due"],
    "coupon_amount_upto_due": ["total_amount", "total amount", "amount_due"],
    "coupon_amount_after_due": ["amount_after_due", "amount after due", "amount after due date"],
}

# Template PDF fields that are computed dynamically by billing_engine.py
COMPUTED_FIELDS: Dict[str, str] = {
    "fixed_charges": "Computed from Sanctioned Load x Rate",
    "energy_charges": "Computed slab-wise from Units",
    "fppca_charges": "Computed percentage of (Fixed + Energy Charges)",
    "total_charges": "Computed sum of Fixed + Energy + FPPCA",
    "total_amount_due": "Computed Total Amount Due",
    "delay_surcharge": "Computed 1.5% overdue surcharge",
    "amount_after_due_date": "Computed Total Amount + Delay Surcharge",
    "headline_due_amount": "Derived from Billing Engine Total Amount Due",
    "donut_energy_charges": "Derived from Energy Charges",
    "donut_fixed_charges": "Derived from Fixed Charges",
    "donut_fppca_charges": "Derived from FPPCA Charges",
    "donut_govt_duty": "Derived from Govt Duty",
    "donut_total_charges": "Derived from Total Charges",
    "bank_account_no": "Derived from Customer ID (TPLAHM + Customer_ID)",
    "bd_energy_charges": "Derived from Energy Charges",
    "bd_fixed_charges": "Derived from Fixed Charges",
    "bd_base_fppas": "Derived from Base FPPAS calculation",
    "bd_fppca_charges": "Derived from FPPCA calculation",
    "bd_total_charges": "Derived from Total Charges",
    "bd_govt_duty": "Derived from Govt Duty calculation",
    "bd_total_amount_due": "Derived from Total Amount Due",
    "bd_delay_surcharge": "Derived from Delay Surcharge",
    "bd_net_amount_after_due": "Derived from Amount After Due Date",
    "billing_message_box": "Generated dynamic billing message",
}

# Excel columns that are used by the billing computation engine even if not directly placed
ENGINE_INPUT_COLUMNS = {
    "units", "consumption", "sanctioned_load", "category", "arrear",
    "other_debit_credit", "prompt_rebate", "advance_rebate", "previous_payment",
    "previous_payment_date", "energy_charges", "fixed_charges", "fppca_charges",
    "total_amount", "amount_after_due", "start_reading", "end_reading", "multiplier"
}


@dataclass
class MappingReport:
    excel_path: str
    excel_headers: List[str]
    total_records: int
    mapped_fields: Dict[str, str]             # PDF variable key -> Excel column or '[Computed]'
    unmapped_excel_columns: List[str]        # Excel headers not used anywhere
    unmapped_pdf_variables: List[str]        # PDF fields with no data source
    warnings: List[str]                      # Informational warnings
    errors: List[str]                        # Blocking errors
    is_valid: bool = True


def _normalize(header: str) -> str:
    return str(header).strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def analyze_mapping(excel_path: str, template: TemplateStructure) -> MappingReport:
    """
    Analyzes an Excel workbook against the detected TemplateStructure.
    Returns a comprehensive MappingReport with matched fields and warnings.
    """
    try:
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        sheet = wb.worksheets[0]
        rows = list(sheet.iter_rows(values_only=True))
    except Exception as exc:
        return MappingReport(
            excel_path=excel_path,
            excel_headers=[],
            total_records=0,
            mapped_fields={},
            unmapped_excel_columns=[],
            unmapped_pdf_variables=[],
            warnings=[],
            errors=[f"Could not read Excel file: {exc}"],
            is_valid=False,
        )

    if not rows:
        return MappingReport(
            excel_path=excel_path,
            excel_headers=[],
            total_records=0,
            mapped_fields={},
            unmapped_excel_columns=[],
            unmapped_pdf_variables=[],
            warnings=[],
            errors=["Excel file is empty."],
            is_valid=False,
        )

    header_row = [str(c).strip() for c in rows[0] if c is not None]
    data_rows = [r for r in rows[1:] if r and any(cell is not None for cell in r)]
    total_records = len(data_rows)

    # Lookup map: normalized header -> original header
    norm_to_original: Dict[str, str] = {}
    for h in header_row:
        norm_to_original[_normalize(h)] = h

    mapped_fields: Dict[str, str] = {}
    used_excel_headers: Set[str] = set()

    template_keys = set(template.fields_by_key.keys())

    # Map each template field
    for key in template_keys:
        aliases = COLUMN_ALIASES.get(key, [key])
        found_header = None
        for alias in aliases:
            norm_alias = _normalize(alias)
            if norm_alias in norm_to_original:
                found_header = norm_to_original[norm_alias]
                break

        if found_header:
            mapped_fields[key] = found_header
            used_excel_headers.add(found_header)
        elif key in COMPUTED_FIELDS:
            mapped_fields[key] = f"[Computed: {COMPUTED_FIELDS[key]}]"

    # Mark engine input columns as used
    for h in header_row:
        norm_h = _normalize(h)
        if norm_h in ENGINE_INPUT_COLUMNS or norm_h in norm_to_original:
            for engine_col in ENGINE_INPUT_COLUMNS:
                if norm_h == engine_col:
                    used_excel_headers.add(h)

    # Identify unmapped Excel columns
    unmapped_excel_columns = [h for h in header_row if h not in used_excel_headers]

    # Identify unmapped PDF variables
    unmapped_pdf_variables = [
        f.key for f in template.fields
        if f.key not in mapped_fields
    ]

    warnings = []
    errors = []

    # Essential fields check
    has_identity = ("customer_id" in mapped_fields) or ("consumer_name" in mapped_fields)
    if not has_identity:
        errors.append("Excel missing essential consumer identity columns (Customer_ID or Consumer_Name).")

    if unmapped_excel_columns:
        warnings.append(
            f"Note: {len(unmapped_excel_columns)} Excel column(s) not mapped to PDF fields: "
            f"{', '.join(unmapped_excel_columns[:5])}{'...' if len(unmapped_excel_columns) > 5 else ''}"
        )

    if unmapped_pdf_variables:
        warnings.append(
            f"Note: {len(unmapped_pdf_variables)} template variable(s) will use default/sample values: "
            f"{', '.join(unmapped_pdf_variables[:5])}{'...' if len(unmapped_pdf_variables) > 5 else ''}"
        )

    is_valid = len(errors) == 0 and total_records > 0

    return MappingReport(
        excel_path=excel_path,
        excel_headers=header_row,
        total_records=total_records,
        mapped_fields=mapped_fields,
        unmapped_excel_columns=unmapped_excel_columns,
        unmapped_pdf_variables=unmapped_pdf_variables,
        warnings=warnings,
        errors=errors,
        is_valid=is_valid,
    )
