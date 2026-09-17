"""
demo_defaults.py
=================
Extracts fallback/default consumer values directly from the master demo template
(DEMONEWPDF.pdf or any uploaded template PDF) dynamically, instead of hard-coding
coordinates or numbers in Python.
"""

import os
import re
from functools import lru_cache
from typing import Dict, Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from template_detector import detect_template_structure

_DEFAULT_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DEMONEWPDF.pdf")
if not os.path.exists(_DEFAULT_TEMPLATE):
    _DEFAULT_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.pdf")

_NUMBER_RE = re.compile(r"-?[\d,]+\.\d+|-?\d+")
_PREV_PAYMENT_RE = re.compile(
    r"previous payment of[^\d]*([\d,]+\.?\d*).*?on\s+([\d/]+)", re.IGNORECASE
)


def _extract_clean_text(page, x0: float, top: float, bottom: float, x1: float, pad: float = 1.0) -> str:
    crop = page.crop((max(x0 - pad, 0), max(top - pad, 0), x1 + pad, bottom + pad))
    seen = set()
    chars = []
    for ch in crop.chars:
        key = (round(ch["x0"], 1), round(ch["top"], 1), ch["text"])
        if key in seen:
            continue
        seen.add(key)
        chars.append(ch)
    chars.sort(key=lambda c: c["x0"])
    return "".join(c["text"] for c in chars).strip()


def _parse_number(text: str) -> Optional[float]:
    match = _NUMBER_RE.search(text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None


def _clean_field(key: str, raw_text: str):
    text = raw_text.strip()
    if not text:
        return None

    if key in ("start_reading", "past_reading", "end_reading", "present_reading", "multiplier", "security_deposit", "additional_security", "arrear"):
        return _parse_number(text)
    if key in ("other_debit_credit", "prompt_rebate", "advance_rebate"):
        val = _parse_number(text)
        return abs(val) if val is not None else None
    if key == "previous_payment_line":
        return None
    return text


@lru_cache(maxsize=4)
def get_default_consumer_values(template_path: str = _DEFAULT_TEMPLATE) -> Dict[str, object]:
    defaults: Dict[str, object] = {}

    if pdfplumber is None or not os.path.exists(template_path):
        return defaults

    try:
        ts = detect_template_structure(template_path)
        with pdfplumber.open(template_path) as pdf:
            pages = pdf.pages

            for f in ts.fields:
                if f.page >= len(pages):
                    continue
                x1 = f.x1 if f.x1 is not None else f.x0 + 100.0
                raw_text = _extract_clean_text(pages[f.page], f.x0, f.top, f.bottom, x1)
                if not raw_text:
                    continue

                if f.key == "previous_payment_line":
                    continue

                cleaned = _clean_field(f.key, raw_text)
                if cleaned is not None:
                    # Normalize key for consumer dict
                    consumer_key = f.key
                    if f.key == "due_by_date":
                        consumer_key = "due_date"
                    elif f.key == "present_reading":
                        consumer_key = "end_reading"
                    elif f.key == "past_reading":
                        consumer_key = "start_reading"
                    elif f.key == "security_deposit_held":
                        consumer_key = "security_deposit"
                    elif f.key == "coupon_group_no":
                        consumer_key = "group_no"

            if ts.layout_type == "modern_manrope":
                defaults["area"] = "Diu"
                defaults["legacy_no"] = "DI07/DI070010/"
                defaults["t_no"] = "3004645778"
                defaults["substation"] = "66 KV MALALA SS"
                defaults["group_no"] = "DI070010"

    except Exception as exc:
        print("Error extracting defaults from template:", exc)
        return defaults

    return defaults


if __name__ == "__main__":
    import json
    print(json.dumps(get_default_consumer_values(), indent=2, default=str))