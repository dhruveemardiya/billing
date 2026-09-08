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
    text = re.sub(r"[^A-Za-z0-9_-]", "", text)
    return text or f"row{fallback_index}"


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
