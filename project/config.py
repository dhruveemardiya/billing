"""
config.py
=========
Single source of truth for every rate, percentage, and path used by the
billing engine and the web application.

Nothing in billing_engine.py or pdf_generator.py should ever contain a
hardcoded number - every tariff rate, rebate percentage, or surcharge
percentage used for calculations lives here so it can be changed in one
place without touching business logic.
"""

import os

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_RUNTIME_DIR = os.path.join(tempfile.gettempdir(), "electricity_bill_generator")
UPLOAD_FOLDER = os.path.join(_RUNTIME_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(_RUNTIME_DIR, "output")

ALLOWED_PDF_EXTENSIONS = {"pdf"}
ALLOWED_EXCEL_EXTENSIONS = {"xlsx", "xls"}

MAX_CONTENT_LENGTH_MB = 25  # Max upload size, in megabytes

# --------------------------------------------------------------------------
# Fixed Charges
# --------------------------------------------------------------------------
# Rs. per kW of sanctioned load, per month.
FIXED_CHARGE_RATE_PER_KW = {
    "DOMESTIC": 10.00,
    "NON-DOMESTIC": 20.00,
    "COMMERCIAL": 20.00,
}
DEFAULT_FIXED_CHARGE_RATE_PER_KW = 10.00

# --------------------------------------------------------------------------
# FPPCA (Fuel & Power Purchase Cost Adjustment)
# --------------------------------------------------------------------------
# Applied on (Fixed Charges + Energy Charges)
FPPCA_PERCENT = 11.08

# --------------------------------------------------------------------------
# Government Electricity Duty
# --------------------------------------------------------------------------
# Applied on (Fixed Charges + Energy Charges + FPPCA Charges)
GOVT_DUTY_PERCENT = 15.0

# --------------------------------------------------------------------------
# Delay Payment Surcharge
# --------------------------------------------------------------------------
# Applied on Total Amount Due, per month overdue. This project applies a
# single month's surcharge (as shown on the bill itself for the upcoming
# due date), matching the "Net Amount After Due Date" figure on the bill.
DELAY_SURCHARGE_PERCENT_PER_MONTH = 1.5

# --------------------------------------------------------------------------
# Energy Charge Slabs (Rs. per unit / kWh), by category
# --------------------------------------------------------------------------
# Each category maps to an ordered list of (slab_upper_bound, rate) tuples.
# slab_upper_bound = None means "and above" (no upper limit).
# Slabs are consumed cumulatively: e.g. for DOMESTIC, the first 50 units are
# billed at 1.70, the next 50 (51-100) at 1.75, and so on.
ENERGY_TARIFF_SLABS = {
    "DOMESTIC": [
        (50, 1.70),
        (100, 1.75),
        (200, 2.50),
        (400, 3.05),
        (None, 3.70),
    ],
    "NON-DOMESTIC": [
        (100, 3.65),
        (None, 4.75),
    ],
    "COMMERCIAL": [
        (100, 3.65),
        (None, 4.75),
    ],
}

# Categories from the Excel sheet are normalized and mapped to a tariff
# slab key above. Anything not found here falls back to DEFAULT_CATEGORY.
CATEGORY_ALIASES = {
    "RESIDENTIAL": "DOMESTIC",
    "DOMESTIC": "DOMESTIC",
    "COMMERCIAL": "COMMERCIAL",
    "NON-DOMESTIC": "NON-DOMESTIC",
    "NON DOMESTIC": "NON-DOMESTIC",
}
DEFAULT_CATEGORY = "DOMESTIC"

# --------------------------------------------------------------------------
# Rounding
# --------------------------------------------------------------------------
CURRENCY_DECIMAL_PLACES = 2

# --------------------------------------------------------------------------
# Dynamic Consumption Variation Range (Direct Billing)
# --------------------------------------------------------------------------
# Percentage variation applied to Reference Units for each generated month.
# e.g., range between -10% and +10% around the reference value.
DEFAULT_UNIT_VARIATION_PERCENT_MIN = 0.04  # Minimum absolute jitter
DEFAULT_UNIT_VARIATION_PERCENT_MAX = 0.11  # Maximum absolute jitter
MINIMUM_DYNAMIC_UNITS = 10                  # Absolute floor for consumed units

# --------------------------------------------------------------------------
# Direct Billing Generation Limits
# --------------------------------------------------------------------------
# Maximum number of billing periods allowed per session.
# Set to None (or 0) for unlimited billing periods generation.
MAX_DIRECT_BILL_PERIODS = None
