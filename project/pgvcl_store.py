"""
pgvcl_store.py
==============
Persistent store for PGVCL customer-specific identifiers.
Generates and persists:
- Meter No: format 'ONE-XXXXXXX' (stable per customer)
- Census Code: valid 8-digit code e.g. 1210XXXX (stable per customer)
- Feeder Code: 1-digit code (stable per customer)
- Route Code: e.g. '3/4/5/XX' (stable per customer)
- Bill No: sequential starting number, incremented for subsequent bills
- Fixed technical codes: Meter Status, M.F., MtrChg Code

Guarantees:
1. Generated once per Customer_ID and persisted to pgvcl_store.json.
2. Same customer always gets the same Meter No, Census, Feeder, Route, and fixed codes.
3. Different customers get distinct random identifiers.
4. Bill No starts at a customer-specific random number and increments sequentially (+0, +1, +2...).
5. Thread-safe with atomic file writes.
"""

import json
import os
import random
import threading
import time
from typing import Dict, Any, Optional

PGVCL_STORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pgvcl_store.json")
_lock = threading.Lock()


def _save_store(data: Dict[str, Any]) -> None:
    """Atomically write PGVCL store to disk."""
    target_dir = os.path.dirname(os.path.abspath(PGVCL_STORE_FILE))
    os.makedirs(target_dir, exist_ok=True)
    temp_file = os.path.join(target_dir, f".{os.path.basename(PGVCL_STORE_FILE)}.tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, PGVCL_STORE_FILE)
    except Exception as exc:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        raise RuntimeError(f"Could not persist PGVCL store to {PGVCL_STORE_FILE}: {exc}")


def _load_store() -> Dict[str, Any]:
    """Load PGVCL store from disk with retry for concurrency."""
    if not os.path.exists(PGVCL_STORE_FILE):
        return {}

    for attempt in range(3):
        try:
            with open(PGVCL_STORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            time.sleep(0.05)

    try:
        with open(PGVCL_STORE_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        data = json.loads(content)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_or_create_pgvcl_customer_data(customer_id: str, period_index: int = 0, custom_inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Retrieves or generates persistent PGVCL customer data for `customer_id`.
    Returns a dictionary containing:
      - meter_no: str (e.g. 'ONE-5797035')
      - census_code: str (e.g. '12104829')
      - feeder_code: str (e.g. '4')
      - route_code: str (e.g. '3/4/5/32')
      - bill_no: str (base_bill_no + period_index)
      - meter_status: str (e.g. '1')
      - mf: str (e.g. '1.0')
      - mtr_chg_code: str (e.g. 'A')
    """
    clean_id = str(customer_id or "").strip()
    if not clean_id:
        clean_id = "DEFAULT_CUSTOMER"

    custom_inputs = custom_inputs or {}

    with _lock:
        store = _load_store()
        rec = store.get(clean_id)
        if not rec or not isinstance(rec, dict):
            # Generate new persistent identifiers for this customer
            # Meter No: e.g. ONE-5797035 (matching PGVCL.jpeg)
            custom_meter = custom_inputs.get("meter_no")
            if custom_meter:
                m_str = str(custom_meter).strip()
                if not m_str.upper().startswith("ONE"):
                    m_str = f"ONE-{m_str}"
                meter_no = m_str
            else:
                meter_no = f"ONE-{random.randint(1000000, 9999999)}"

            # Census Code: 8 digits, e.g. 1210XXXX
            custom_census = custom_inputs.get("census_code")
            census_code = str(custom_census).strip() if custom_census else f"1210{random.randint(1000, 9999)}"

            # Feeder Code: single digit 1-9
            custom_feeder = custom_inputs.get("feeder_code")
            feeder_code = str(custom_feeder).strip() if custom_feeder else str(random.choice([1, 2, 3, 4, 5, 6, 7]))

            # Route Code: e.g. 3/4/5/32
            custom_route = custom_inputs.get("route_code")
            route_code = str(custom_route).strip() if custom_route else f"3/4/5/{random.randint(10, 48)}"

            # Base Bill No: 10-digit sequential starting number, e.g. 3004406980
            custom_bill = custom_inputs.get("bill_no")
            if custom_bill and str(custom_bill).strip().isdigit() and len(str(custom_bill).strip()) >= 6:
                base_bill_no = int(str(custom_bill).strip())
            else:
                base_bill_no = random.randint(3004100000, 3004899999)

            rec = {
                "customer_id": clean_id,
                "meter_no": meter_no,
                "census_code": census_code,
                "feeder_code": feeder_code,
                "route_code": route_code,
                "base_bill_no": base_bill_no,
                "meter_status": str(custom_inputs.get("meter_status") or "1"),
                "mf": str(custom_inputs.get("mf") or "1.0"),
                "mtr_chg_code": str(custom_inputs.get("mtr_chg_code") or "A"),
            }
            store[clean_id] = rec
            _save_store(store)
        else:
            # Update fixed fields if explicitly provided
            updated = False
            for k in ("meter_status", "mf", "mtr_chg_code"):
                if custom_inputs.get(k):
                    rec[k] = str(custom_inputs[k])
                    updated = True
            if custom_inputs.get("meter_no"):
                m_str = str(custom_inputs["meter_no"]).strip()
                if not m_str.upper().startswith("ONE"):
                    m_str = f"ONE-{m_str}"
                rec["meter_no"] = m_str
                updated = True
            if updated:
                store[clean_id] = rec
                _save_store(store)

        # Compute sequential bill number for period_index
        base_bill = int(rec.get("base_bill_no", 3004406980))
        current_bill_no = str(base_bill + period_index)

        return {
            "meter_no": rec["meter_no"],
            "census_code": rec["census_code"],
            "feeder_code": rec["feeder_code"],
            "route_code": rec["route_code"],
            "bill_no": current_bill_no,
            "meter_status": rec.get("meter_status", "1"),
            "mf": rec.get("mf", "1.0"),
            "mtr_chg_code": rec.get("mtr_chg_code", "A"),
        }
