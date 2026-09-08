"""
demo_defaults.py
=================
Builds the "fallback" consumer values used by excel_reader.py by reading
them straight out of demo.pdf, instead of hard-coding a snapshot of numbers
in Python.

Why: demo.pdf already ships with a fully-filled sample bill baked into it
(consumer "RAMAJI BHAGVAN", meter DND52642, etc). If that template PDF is
ever replaced/updated, the defaults used for missing Excel columns should
follow automatically - so we crop each value straight off the template
using the exact bounding boxes pdf_mapper.py already defines for those
fields, instead of keeping a second, easily-stale copy of the same numbers
in code.

Usage:
    from demo_defaults import get_default_consumer_values
    defaults = get_default_consumer_values()   # cached after first call

If demo.pdf is missing, unreadable, or a particular value can't be parsed,
that key is simply left out of the returned dict - excel_reader.py's
_apply_defaults() only overrides fields that ARE present, so a missing
default just means that one field stays blank instead of crashing anything.
"""

import os
import re
from functools import lru_cache
from typing import Dict, Optional

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.pdf")

# (page_index, x0, top, bottom, x1) - same bounding boxes pdf_mapper.py uses
# to place its overlay text, reused here to read the template's own sample
# values back out.
_FIELD_BOXES = {
    "area": (0, 275.0, 34.1, 41.1, 340),
    "bill_no": (0, 275.0, 54.1, 61.1, 340),          # "T. No." box -> bill_no
    "billing_mode": (0, 275.0, 64.1, 71.1, 340),
    "legacy_no": (0, 275.0, 74.1, 81.1, 340),
    "category": (0, 209.2, 172.2, 180.2, 300),
    "billing_month": (0, 316.6, 172.2, 180.2, 430),
    "supply_type": (0, 209.2, 207.7, 215.7, 300),
    "reading_date": (0, 316.6, 207.7, 215.7, 430),
    "sanctioned_load": (0, 209.2, 244.3, 252.3, 300),
    "bill_date": (0, 316.6, 244.3, 252.3, 430),
    "substation": (0, 435.4, 244.3, 252.3, 543),
    "previous_payment_line": (0, 198.8, 294.3, 303.4, 543),
    "due_date": (0, 198.8, 343.2, 351.2, 300),        # "DUE BY" box
    "security_deposit": (0, 321.5, 345.3, 353.4, 430),
    "additional_security": (0, 439.0, 345.3, 353.4, 543),
    "meter_no": (0, 63.2, 418.5, 425.5, 116),
    "end_reading": (0, 80.0, 436.0, 443.0, 116),      # "present reading" box
    "start_reading": (0, 80.0, 455.0, 462.0, 116),    # "past reading" box
    "multiplier": (0, 89.0, 470.2, 477.2, 116),
    "arrear": (1, 237.6, 137.3, 144.3, 277.2),
    "other_debit_credit": (1, 261.7, 156.3, 163.3, 277.2),
    "prompt_rebate": (1, 260.4, 175.3, 182.3, 277.2),
    "advance_rebate": (1, 261.7, 194.3, 201.3, 277.2),
    "group_no": (1, 44.9, 820.6, 826.6, 130),
}

_NUMBER_RE = re.compile(r"-?[\d,]+\.\d+|-?\d+")
_PREV_PAYMENT_RE = re.compile(
    r"previous payment of[^\d]*([\d,]+\.\d+).*?on\s+([\d/]+)", re.IGNORECASE
)


def _extract_clean_text(page, x0: float, top: float, bottom: float, x1: float, pad: float = 1.0) -> str:
    """
    Crop the given box and rebuild its text char-by-char, deduplicating any
    characters that sit at the exact same position (demo.pdf has a couple of
    fields with an overlapping duplicate text layer, which otherwise garbles
    extract_text() output, e.g. '0.00' + '0.00' -> '00..0000').
    """
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
    """Turn a raw cropped string into the value excel_reader expects for `key`."""
    text = raw_text.strip()
    if not text:
        return None

    if key == "start_reading":
        # template shows "- 9392"
        return _parse_number(text)
    if key == "end_reading":
        return _parse_number(text)
    if key == "multiplier":
        # template shows "x 1.00"
        return _parse_number(text)
    if key in ("security_deposit", "additional_security"):
        # template shows "$7,128.00" / "$0"
        return _parse_number(text)
    if key == "arrear":
        # template shows "Credit: -2.29" (a plain positive number for a debit)
        return _parse_number(text)
    if key in ("other_debit_credit", "prompt_rebate", "advance_rebate"):
        value = _parse_number(text)
        return abs(value) if value is not None else None
    if key == "previous_payment_line":
        return None  # handled separately, see below
    # everything else (dates, text labels, category, etc.) is used as-is
    return text


@lru_cache(maxsize=1)
def get_default_consumer_values(template_path: str = _TEMPLATE_PATH) -> Dict[str, object]:
    """
    Read demo.pdf and return a dict of default consumer-field values, keyed
    the same way excel_reader.py's internal consumer dict is (e.g.
    "billing_month", "start_reading", "security_deposit", ...).

    Cached after the first call - the template doesn't change mid-run.
    """
    defaults: Dict[str, object] = {}

    if pdfplumber is None or not os.path.exists(template_path):
        return defaults

    try:
        with pdfplumber.open(template_path) as pdf:
            pages = pdf.pages

            for key, (page_idx, x0, top, bottom, x1) in _FIELD_BOXES.items():
                if page_idx >= len(pages):
                    continue
                raw_text = _extract_clean_text(pages[page_idx], x0, top, bottom, x1)
                if not raw_text:
                    continue

                if key == "previous_payment_line":
                    match = _PREV_PAYMENT_RE.search(raw_text)
                    if match:
                        amount_str, date_str = match.groups()
                        try:
                            defaults["previous_payment"] = float(amount_str.replace(",", ""))
                        except ValueError:
                            pass
                        defaults["previous_payment_date"] = date_str
                    continue

                cleaned = _clean_field(key, raw_text)
                if cleaned is not None:
                    defaults[key] = cleaned

    except Exception:
        # Never let a bad/unexpected template break bill generation - just
        # fall back to whatever defaults we managed to extract (or none).
        return defaults

    return defaults


if __name__ == "__main__":
    import json
    print(json.dumps(get_default_consumer_values(), indent=2, default=str))