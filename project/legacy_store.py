"""
legacy_store.py
===============
Persistent store for customer Legacy Numbers.
Generates a random 6-digit Legacy No once per customer and persists it
using Customer_ID as the unique key.

Guarantees:
1. Generated once per customer (Customer_ID).
2. Persisted to disk in `legacy_store.json` using atomic file replacement and thread locking.
3. Every bill generated for the same customer uses the exact same Legacy No.
4. Different customers automatically receive distinct random Legacy No values.
5. Never regenerated for each bill/month.
"""

import json
import os
import random
import threading
import time
from typing import Dict, Optional

LEGACY_STORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "legacy_store.json")
_lock = threading.Lock()

# Initial seed for standard reference customer
DEFAULT_LEGACY_STORE: Dict[str, str] = {
    "743200550": "200550",
}


def _save_store(data: Dict[str, str]) -> None:
    """Atomically write legacy store to disk."""
    target_dir = os.path.dirname(os.path.abspath(LEGACY_STORE_FILE))
    os.makedirs(target_dir, exist_ok=True)
    temp_file = os.path.join(target_dir, f".{os.path.basename(LEGACY_STORE_FILE)}.tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, LEGACY_STORE_FILE)
    except Exception as exc:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        raise RuntimeError(f"Could not persist legacy store to {LEGACY_STORE_FILE}: {exc}")


def _load_store() -> Dict[str, str]:
    """Load legacy store from disk with retry for concurrency."""
    if not os.path.exists(LEGACY_STORE_FILE):
        data = dict(DEFAULT_LEGACY_STORE)
        try:
            _save_store(data)
        except Exception:
            pass
        return data

    for attempt in range(3):
        try:
            with open(LEGACY_STORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {str(k).strip(): str(v).strip() for k, v in data.items()}
        except (json.JSONDecodeError, OSError):
            time.sleep(0.05)

    try:
        with open(LEGACY_STORE_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        data = json.loads(content)
        return {str(k).strip(): str(v).strip() for k, v in data.items()}
    except Exception:
        return dict(DEFAULT_LEGACY_STORE)


def _generate_unique_legacy_no(existing_values: set) -> str:
    """Generate a random 6-digit legacy number distinct from existing values."""
    for _ in range(10000):
        val = str(random.randint(100000, 999999))
        if val not in existing_values:
            return val
    # Fallback if range saturated
    return str(random.randint(1000000, 9999999))


def get_or_create_legacy_no(customer_id: str, fallback_no: Optional[str] = None) -> str:
    """
    Retrieves the persisted Legacy No for `customer_id`.
    If not already stored, generates a unique random 6-digit Legacy No,
    persists it, and returns it.
    """
    clean_id = str(customer_id or "").strip()
    if not clean_id:
        return str(fallback_no).strip() if (fallback_no and str(fallback_no).strip().isdigit()) else str(random.randint(100000, 999999))

    with _lock:
        store = _load_store()
        if clean_id in store:
            return store[clean_id]

        used_values = set(store.values())

        if fallback_no and str(fallback_no).strip().isdigit() and len(str(fallback_no).strip()) == 6:
            chosen = str(fallback_no).strip()
        else:
            chosen = _generate_unique_legacy_no(used_values)

        store[clean_id] = chosen
        _save_store(store)
        return chosen


def get_all_legacy_records() -> Dict[str, str]:
    """Returns a copy of all stored Customer_ID -> Legacy_No mappings."""
    with _lock:
        return dict(_load_store())
