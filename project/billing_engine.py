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
    govt_duty: float = 0.0
    charges_before_duty: float = 0.0
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


def calculate_govt_duty(fixed_charges, energy_charges, fppca_charges):
    duty_pct = getattr(config, "GOVT_DUTY_PERCENT", 15.0)
    return _round((fixed_charges + energy_charges + fppca_charges) * (duty_pct / 100.0))


def calculate_total_charges(fixed_charges, energy_charges, fppca_charges, govt_duty=0.0):
    return _round(fixed_charges + energy_charges + fppca_charges + govt_duty)


def calculate_total_amount_due(total_charges, arrear, other_debit_credit, prompt_rebate, advance_rebate):
    return _round(total_charges + arrear + other_debit_credit - prompt_rebate - advance_rebate)


def calculate_delay_surcharge(total_amount_due):
    return _round(total_amount_due * (config.DELAY_SURCHARGE_PERCENT_PER_MONTH / 100.0))


def calculate_amount_after_due_date(total_amount_due, delay_surcharge):
    return _round(total_amount_due + delay_surcharge)


def compute_bill(consumer: dict) -> BillCalculation:
    sanctioned_load_kw = parse_sanctioned_load(consumer.get("sanctioned_load"))
    units = float(consumer.get("units") or 0)
    category_key = resolve_category_key(consumer.get("category", ""))

    # Energy charges & slab breakdown
    calc_energy, breakdown = calculate_energy_charges(units, category_key)
    if consumer.get("energy_charges") is not None:
        try:
            energy_charges = _round(consumer["energy_charges"])
        except (ValueError, TypeError):
            energy_charges = calc_energy
    else:
        energy_charges = calc_energy

    # Fixed charges
    calc_fixed = calculate_fixed_charges(sanctioned_load_kw, category_key)
    if consumer.get("fixed_charges") is not None:
        try:
            fixed_charges = _round(consumer["fixed_charges"])
        except (ValueError, TypeError):
            fixed_charges = calc_fixed
    else:
        fixed_charges = calc_fixed

    # FPPCA charges
    calc_fppca = calculate_fppca(fixed_charges, energy_charges)
    if consumer.get("fppca_charges") is not None:
        try:
            fppca_charges = _round(consumer["fppca_charges"])
        except (ValueError, TypeError):
            fppca_charges = calc_fppca
    else:
        fppca_charges = calc_fppca

    # Government duty
    calc_govt_duty = calculate_govt_duty(fixed_charges, energy_charges, fppca_charges)
    if consumer.get("govt_duty") is not None:
        try:
            govt_duty = _round(consumer["govt_duty"])
        except (ValueError, TypeError):
            govt_duty = calc_govt_duty
    else:
        govt_duty = calc_govt_duty

    charges_before_duty = _round(fixed_charges + energy_charges + fppca_charges)
    total_charges = _round(charges_before_duty + govt_duty)

    arrear = float(consumer.get("arrear", 0) or 0)
    other_debit_credit = float(consumer.get("other_debit_credit", 0) or 0)
    prompt_rebate = float(consumer.get("prompt_rebate", 0) or 0)
    advance_rebate = float(consumer.get("advance_rebate", 0) or 0)

    computed_total_due = calculate_total_amount_due(total_charges, arrear, other_debit_credit, prompt_rebate, advance_rebate)

    # Use Excel total if provided, otherwise computed
    if consumer.get("total_amount") is not None:
        try:
            total_amount_due = _round(consumer["total_amount"])
        except (ValueError, TypeError):
            total_amount_due = computed_total_due
    else:
        total_amount_due = computed_total_due

    # Bill Total Reconciliation (Requirement 7)
    sum_of_components = _round(fixed_charges + energy_charges + fppca_charges + govt_duty)
    expected_bill_total = _round(sum_of_components + arrear + other_debit_credit - prompt_rebate - advance_rebate)
    mismatch = abs(total_amount_due - expected_bill_total)
    if mismatch > 0.01:
        print(f"[RECONCILIATION WARNING] Mismatch detected: Final Bill Total={total_amount_due:.2f}, "
              f"Sum of Components={expected_bill_total:.2f}, Diff={total_amount_due - expected_bill_total:.2f}. "
              f"Components: Fixed={fixed_charges}, Energy={energy_charges}, FPPAS={fppca_charges}, "
              f"Govt Duty={govt_duty}, Arrear={arrear}, Other={other_debit_credit}")
        # If total_amount in Excel was missing or slightly off, bind to exact sum
        if consumer.get("total_amount") is None:
            total_amount_due = expected_bill_total

    # Delay surcharge
    if consumer.get("delayed_payment_charges") is not None:
        try:
            delay_surcharge = _round(consumer["delayed_payment_charges"])
        except (ValueError, TypeError):
            delay_surcharge = calculate_delay_surcharge(total_amount_due)
    else:
        delay_surcharge = calculate_delay_surcharge(total_amount_due)

    if consumer.get("amount_after_due") is not None:
        try:
            amount_after_due_date = _round(consumer["amount_after_due"])
        except (ValueError, TypeError):
            amount_after_due_date = calculate_amount_after_due_date(total_amount_due, delay_surcharge)
    else:
        amount_after_due_date = calculate_amount_after_due_date(total_amount_due, delay_surcharge)

    return BillCalculation(
        sanctioned_load_kw=sanctioned_load_kw,
        units_consumed=units,
        category_key=category_key,
        fixed_charges=fixed_charges,
        energy_charges=energy_charges,
        energy_slab_breakdown=breakdown,
        fppca_charges=fppca_charges,
        govt_duty=govt_duty,
        charges_before_duty=charges_before_duty,
        total_charges=total_charges,
        arrear=arrear,
        other_debit_credit=other_debit_credit,
        prompt_rebate=prompt_rebate,
        advance_rebate=advance_rebate,
        total_amount_due=total_amount_due,
        delay_surcharge=delay_surcharge,
        amount_after_due_date=amount_after_due_date,
    )