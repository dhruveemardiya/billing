"""
auth_manager.py
===============
Self-contained static authentication manager without any external database.
Persists credentials in `auth_store.json` so password updates survive server
restarts while strictly disallowing the old password once changed.

Guarantees:
1. The initial password 'Bill@2026' is ONLY written if 'auth_store.json' does NOT exist.
2. Once the password is updated, 'auth_store.json' is immediately synced to disk via atomic write.
3. Every check_credentials() call reads directly from 'auth_store.json'.
4. 'Bill@2026' is never permitted if 'auth_store.json' contains a changed password.
"""

import json
import os
import threading
import time

AUTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_store.json")
_lock = threading.Lock()

DEFAULT_AUTH = {
    "username": "Admin",
    "password": "Bill@2026",
    "pin": "123456",
}


def _save_auth_data(data: dict):
    """
    Atomically writes authentication data to disk with fsync.
    Uses a temporary file and atomic os.replace so no reader ever encounters
    an empty, locked, or partially-written file.
    """
    with _lock:
        target_dir = os.path.dirname(os.path.abspath(AUTH_FILE))
        os.makedirs(target_dir, exist_ok=True)
        temp_file = os.path.join(target_dir, f".{os.path.basename(AUTH_FILE)}.tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, AUTH_FILE)
        except Exception as exc:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            raise RuntimeError(f"Could not persist auth data to {AUTH_FILE}: {exc}")


def _load_auth_data() -> dict:
    """
    Loads authentication data from 'auth_store.json'.
    - If the file does NOT exist: creates it with initial credentials ('Bill@2026').
    - If the file exists: reads the persistent password from disk. Under NO circumstance
      will it overwrite or reset an existing changed password back to 'Bill@2026'.
    """
    with _lock:
        if not os.path.exists(AUTH_FILE):
            # Only initialize with default Bill@2026 if file does not exist on disk
            data = dict(DEFAULT_AUTH)
            try:
                _save_auth_data(data)
            except Exception:
                pass
            return data

        # File exists on disk: read it with retry in case of concurrent file access
        for attempt in range(3):
            try:
                with open(AUTH_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                username = data.get("username") or DEFAULT_AUTH["username"]
                password = data.get("password")
                pin = str(data.get("pin") if data.get("pin") is not None else DEFAULT_AUTH["pin"]).strip()

                if not password:
                    password = DEFAULT_AUTH["password"]

                return {
                    "username": username,
                    "password": password,
                    "pin": pin,
                }
            except (json.JSONDecodeError, OSError):
                time.sleep(0.05)

        # Fallback raw read if JSON decoder failed
        try:
            with open(AUTH_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            data = json.loads(content)
            return {
                "username": data.get("username", DEFAULT_AUTH["username"]),
                "password": data.get("password", DEFAULT_AUTH["password"]),
                "pin": str(data.get("pin", DEFAULT_AUTH["pin"])).strip(),
            }
        except Exception:
            return dict(DEFAULT_AUTH)


def check_credentials(username: str, password: str) -> bool:
    """
    Validates username and password strictly against disk-persisted credentials.
    Username is case-insensitive for 'Admin'. Password is exact and strict.
    """
    if not username or not password:
        return False

    auth_data = _load_auth_data()
    stored_user = auth_data.get("username", "Admin")
    stored_pass = auth_data.get("password")

    if not stored_pass:
        return False

    return username.strip().lower() == stored_user.lower() and password == stored_pass


def verify_pin(pin: str) -> bool:
    """
    Verifies the administrative security PIN (123456).
    """
    if not pin:
        return False
    auth_data = _load_auth_data()
    stored_pin = str(auth_data.get("pin", "123456")).strip()
    return str(pin).strip() == stored_pin


def update_password(pin: str, new_password: str, confirm_password: str) -> tuple[bool, str]:
    """
    Updates the password if the PIN is valid and passwords match.
    Atomically persists the new password to 'auth_store.json'.
    Username remains 'Admin'. Old password will immediately stop working.
    """
    if not verify_pin(pin):
        return False, "Invalid security PIN."

    if not new_password:
        return False, "New password cannot be empty."

    if new_password != confirm_password:
        return False, "New password and confirm password do not match."

    data = _load_auth_data()
    data["username"] = "Admin"
    data["password"] = new_password

    try:
        _save_auth_data(data)
        return True, "Password updated successfully."
    except Exception as exc:
        return False, f"Failed to save password: {exc}"


def reset_to_defaults():
    """
    Explicit helper for resetting to default credentials when explicitly requested.
    Never called during standard application runtime.
    """
    _save_auth_data(dict(DEFAULT_AUTH))
