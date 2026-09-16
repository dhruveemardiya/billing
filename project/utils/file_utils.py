"""
utils/file_utils.py
====================
Small, dependency-free helper functions used by app.py: safe filename
generation and zipping a folder of generated invoices for download.
"""

import os
import re
import zipfile


def safe_customer_id(raw_value, fallback_index: int) -> str:
    """Turn a customer id into something safe to use in a filename."""
    text = str(raw_value or "").strip()
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or f"row{fallback_index}"


MONTH_FULL_NAMES = {
    "jan": "January", "feb": "February", "mar": "March", "apr": "April",
    "may": "May", "jun": "June", "jul": "July", "aug": "August",
    "sep": "September", "oct": "October", "nov": "November", "dec": "December"
}


def extract_billing_month_tag(consumer: dict) -> str:
    """
    Extract a standardized billing month tag (e.g. 'January_2026', 'March_2026')
    from the consumer record. Checks 'billing_month', then 'bill_date', 'reading_date', 'due_date'.
    """
    from pdf_mapper import _parse_billing_month

    for key in ("billing_month", "bill_date", "reading_date", "due_date"):
        val = consumer.get(key)
        if val is not None and str(val).strip():
            month_abbr, year = _parse_billing_month(val)
            if month_abbr and year:
                full_month = MONTH_FULL_NAMES.get(month_abbr.lower(), month_abbr.capitalize())
                return f"{full_month}_{year}"
            cleaned = str(val).strip().replace(" ", "_").replace("/", "-")
            if cleaned:
                return cleaned
    return ""


def build_bill_filename(
    consumer: dict,
    index: int,
    total_consumers: int = 1,
    month_counts: dict = None,
    used_filenames: set = None,
) -> str:
    """
    Build a standard bill filename according to the billing month (e.g. 'January_2026.pdf').
    If multiple consumers share the same month in a batch, disambiguates cleanly
    with customer_id or index (e.g. 'January_2026_743200550.pdf').
    """
    filename_source = consumer.get("customer_id") or consumer.get("consumer_name")
    customer_id = safe_customer_id(filename_source, index)
    month_tag = extract_billing_month_tag(consumer)

    if month_tag:
        is_shared_month = month_counts and month_counts.get(month_tag, 1) > 1
        if not is_shared_month:
            base_filename = f"{month_tag}.pdf"
        else:
            base_filename = f"{month_tag}_{customer_id}.pdf"
    else:
        base_filename = f"Invoice_{customer_id}_{index}.pdf"

    if used_filenames is not None:
        final_filename = base_filename
        if final_filename in used_filenames:
            stem, ext = os.path.splitext(base_filename)
            final_filename = f"{stem}_{index}{ext}"
        used_filenames.add(final_filename)
        return final_filename

    return base_filename


def zip_directory(source_dir: str, zip_path: str) -> str:
    """Zip every file directly inside source_dir into zip_path."""
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in sorted(os.listdir(source_dir)):
            file_path = os.path.join(source_dir, filename)
            if os.path.isfile(file_path):
                zf.write(file_path, arcname=filename)
    return zip_path


def clear_directory(directory: str) -> None:
    """Remove all files inside a directory (does not remove the directory itself)."""
    if not os.path.isdir(directory):
        return
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
