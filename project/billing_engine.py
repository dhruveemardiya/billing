"""
billing_engine.py
==================
Pure calculation logic for turning raw consumer readings into a fully
computed electricity bill. No PDF, Excel, or web-framework code lives here -
this module only takes numbers/strings in and returns numbers out, which
makes it trivially unit-testable.

Every formula mirrors the official billing rules supplied for this project:

    Fixed Charges   = Sanctioned Load x Fixed Charge Rate
    Energy Charges  = slab-wise consumption calculation
    FPPCA           = (Fixed Charges + Energy Charges) x FPPCA %
    Total Charges   = Fixed Charges + Energy Charges + FPPCA
    Total Amount    = Total Charges + Arrear + Other Debit/Credit
                      - Prompt Rebate - Advance Rebate
    Amount After Due Date = Total Amount + Delay Payment Surcharge
"""
import re
from dataclasses import dataclass, field
from typing import List, Tuple
import config


@dataclass
class BillCalculation:
    sanctioned_load_kw: float
    units_consumed: float
    category_key: str
    fixed_charges: float = 0.0
    energy_charges: float = 0.0
    energy_slab_breakdown: List[Tuple[str, float, float, float]] = field(default_factory=list)
    fppca_charges: float = 0.0
    total_charges: float = 0.0
    arrear: float = 0.0
    other_debit_credit: float = 0.0
    prompt_rebate: float = 0.0
    advance_rebate: float = 0.0
    total_amount_due: float = 0.0
    delay_surcharge: float = 0.0
    amount_after_due_date: float = 0.0


def _round(value):
    return round(float(value), config.CURRENCY_DECIMAL_PLACES)


def parse_sanctioned_load(raw_value):
    if raw_value is None:
        return 0.0
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    text = str(raw_value).strip()
    match = re.search(r"[\d.]+", text)
    return float(match.group()) if match else 0.0


def resolve_category_key(category_name):
    normalized = str(category_name).strip().upper()
    return config.CATEGORY_ALIASES.get(normalized, config.DEFAULT_CATEGORY)


def calculate_fixed_charges(sanctioned_load_kw, category_key):
    rate = config.FIXED_CHARGE_RATE_PER_KW.get(category_key, config.DEFAULT_FIXED_CHARGE_RATE_PER_KW)
    return _round(sanctioned_load_kw * rate)


def calculate_energy_charges(units, category_key):
    slabs = config.ENERGY_TARIFF_SLABS.get(category_key, config.ENERGY_TARIFF_SLABS[config.DEFAULT_CATEGORY])
    remaining_units = float(units)
    lower_bound = 0
    total = 0.0
    breakdown = []
    for upper_bound, rate in slabs:
        if remaining_units <= 0:
            break
        if upper_bound is None:
            units_in_slab = remaining_units
        else:
            units_in_slab = min(remaining_units, upper_bound - lower_bound)
        if units_in_slab <= 0:
            lower_bound = upper_bound if upper_bound is not None else lower_bound
            continue
        amount = units_in_slab * rate
        total += amount
        breakdown.append((f"{lower_bound+1}-{upper_bound}", units_in_slab, rate, _round(amount)))
        remaining_units -= units_in_slab
        lower_bound = upper_bound if upper_bound is not None else lower_bound
    return _round(total), breakdown


def calculate_fppca(fixed_charges, energy_charges):
    return _round((fixed_charges + energy_charges) * (config.FPPCA_PERCENT / 100.0))


def calculate_total_charges(fixed_charges, energy_charges, fppca_charges):
    return _round(fixed_charges + energy_charges + fppca_charges)


def calculate_total_amount_due(total_charges, arrear, other_debit_credit, prompt_rebate, advance_rebate):
    return _round(total_charges + arrear + other_debit_credit - prompt_rebate - advance_rebate)


def calculate_delay_surcharge(total_amount_due):
    return _round(total_amount_due * (config.DELAY_SURCHARGE_PERCENT_PER_MONTH / 100.0))


def calculate_amount_after_due_date(total_amount_due, delay_surcharge):
    return _round(total_amount_due + delay_surcharge)


def compute_bill(consumer):
    sanctioned_load_kw = parse_sanctioned_load(consumer.get("sanctioned_load"))
    units = float(consumer.get("units") or 0)
    category_key = resolve_category_key(consumer.get("category", ""))
    fixed_charges = calculate_fixed_charges(sanctioned_load_kw, category_key)
    energy_charges, breakdown = calculate_energy_charges(units, category_key)
    fppca_charges = calculate_fppca(fixed_charges, energy_charges)
    total_charges = calculate_total_charges(fixed_charges, energy_charges, fppca_charges)
    arrear = float(consumer.get("arrear", 0) or 0)
    other_debit_credit = float(consumer.get("other_debit_credit", 0) or 0)
    prompt_rebate = float(consumer.get("prompt_rebate", 0) or 0)
    advance_rebate = float(consumer.get("advance_rebate", 0) or 0)
    total_amount_due = calculate_total_amount_due(total_charges, arrear, other_debit_credit, prompt_rebate, advance_rebate)
    delay_surcharge = calculate_delay_surcharge(total_amount_due)
    amount_after_due_date = calculate_amount_after_due_date(total_amount_due, delay_surcharge)
    return BillCalculation(
        sanctioned_load_kw=sanctioned_load_kw, units_consumed=units, category_key=category_key,
        fixed_charges=fixed_charges, energy_charges=energy_charges, energy_slab_breakdown=breakdown,
        fppca_charges=fppca_charges, total_charges=total_charges, arrear=arrear,
        other_debit_credit=other_debit_credit, prompt_rebate=prompt_rebate, advance_rebate=advance_rebate,
        total_amount_due=total_amount_due, delay_surcharge=delay_surcharge,
        amount_after_due_date=amount_after_due_date,
    )