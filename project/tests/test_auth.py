import unittest
import os
import tempfile
import json
import auth_manager


class TestAuthManager(unittest.TestCase):
    def setUp(self):
        # Use an isolated temporary auth file so tests NEVER overwrite production auth_store.json
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.temp_file.close()
        self.orig_auth_file = auth_manager.AUTH_FILE
        auth_manager.AUTH_FILE = self.temp_file.name
        auth_manager._save_auth_data(dict(auth_manager.DEFAULT_AUTH))

    def tearDown(self):
        auth_manager.AUTH_FILE = self.orig_auth_file
        if os.path.exists(self.temp_file.name):
            try:
                os.remove(self.temp_file.name)
            except Exception:
                pass

    def test_default_login_success(self):
        self.assertTrue(auth_manager.check_credentials("Admin", "Bill@2026"))
        self.assertTrue(auth_manager.check_credentials("admin", "Bill@2026"))

    def test_wrong_credentials(self):
        self.assertFalse(auth_manager.check_credentials("Admin", "wrong_pass"))
        self.assertFalse(auth_manager.check_credentials("User", "Bill@2026"))
        self.assertFalse(auth_manager.check_credentials("", ""))

    def test_pin_verification(self):
        self.assertTrue(auth_manager.verify_pin("123456"))
        self.assertTrue(auth_manager.verify_pin(123456))
        self.assertFalse(auth_manager.verify_pin("000000"))
        self.assertFalse(auth_manager.verify_pin(""))

    def test_password_update_flow(self):
        # 1. Try with wrong PIN
        success, msg = auth_manager.update_password("999999", "NewPass@123", "NewPass@123")
        self.assertFalse(success)

        # 2. Try with mismatched passwords
        success, msg = auth_manager.update_password("123456", "Pass1", "Pass2")
        self.assertFalse(success)

        # 3. Successful update
        success, msg = auth_manager.update_password("123456", "NewSecret@2026", "NewSecret@2026")
        self.assertTrue(success)

        # 4. Old password must NO LONGER work
        self.assertFalse(auth_manager.check_credentials("Admin", "Bill@2026"))

        # 5. New password must work
        self.assertTrue(auth_manager.check_credentials("Admin", "NewSecret@2026"))

    def test_password_persists_to_disk_and_restart(self):
        # Update password
        success, _ = auth_manager.update_password("123456", "RestartSafe@2026", "RestartSafe@2026")
        self.assertTrue(success)

        # Re-read raw disk file to simulate complete application restart
        with open(auth_manager.AUTH_FILE, "r", encoding="utf-8") as f:
            disk_data = json.load(f)

        self.assertEqual(disk_data["username"], "Admin")
        self.assertEqual(disk_data["password"], "RestartSafe@2026")
        self.assertNotEqual(disk_data["password"], "Bill@2026")

        # Calling _load_auth_data directly (as during restart) must NOT reset to Bill@2026
        reloaded_data = auth_manager._load_auth_data()
        self.assertEqual(reloaded_data["password"], "RestartSafe@2026")

        # Function check after disk read
        self.assertTrue(auth_manager.check_credentials("Admin", "RestartSafe@2026"))
        self.assertFalse(auth_manager.check_credentials("Admin", "Bill@2026"))


if __name__ == "__main__":
    unittest.main()
