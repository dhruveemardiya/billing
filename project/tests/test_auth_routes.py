import unittest
import os
import tempfile
import json
import auth_manager
from app import app


class TestAuthRoutes(unittest.TestCase):
    def setUp(self):
        # Use an isolated temporary auth file so tests NEVER touch production auth_store.json
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.temp_file.close()
        self.orig_auth_file = auth_manager.AUTH_FILE
        auth_manager.AUTH_FILE = self.temp_file.name
        auth_manager._save_auth_data(dict(auth_manager.DEFAULT_AUTH))

        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        auth_manager.AUTH_FILE = self.orig_auth_file
        if os.path.exists(self.temp_file.name):
            try:
                os.remove(self.temp_file.name)
            except Exception:
                pass

    def test_unauthenticated_redirect_to_login(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_login_page_renders(self):
        resp = self.client.get("/login")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Sign In", resp.data)
        self.assertIn(b"root", resp.data)

    def test_login_invalid_credentials(self):
        resp = self.client.post(
            "/api/login",
            data=json.dumps({"username": "Admin", "password": "WrongPassword"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)
        data = json.loads(resp.data)
        self.assertFalse(data.get("success"))
        self.assertIn("Invalid", data.get("error", ""))

    def test_login_valid_default_credentials(self):
        resp = self.client.post(
            "/api/login",
            data=json.dumps({"username": "Admin", "password": "Bill@2026"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data.get("success"))

        # Accessing / should now succeed
        home_resp = self.client.get("/")
        self.assertEqual(home_resp.status_code, 200)
        self.assertIn(b"Electricity Bill Generator", home_resp.data)

    def test_pin_verification(self):
        # Invalid PIN
        resp = self.client.post(
            "/api/verify-pin",
            data=json.dumps({"pin": "999999"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

        # Valid PIN
        resp_ok = self.client.post(
            "/api/verify-pin",
            data=json.dumps({"pin": "123456"}),
            content_type="application/json",
        )
        self.assertEqual(resp_ok.status_code, 200)

    def test_password_reset_and_persistence_flow(self):
        # Reset password
        resp = self.client.post(
            "/api/reset-password",
            data=json.dumps({
                "pin": "123456",
                "new_password": "NewSecurePass#2026",
                "confirm_password": "NewSecurePass#2026",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data.get("success"))

        # Old password Bill@2026 must NO LONGER work
        old_resp = self.client.post(
            "/api/login",
            data=json.dumps({"username": "Admin", "password": "Bill@2026"}),
            content_type="application/json",
        )
        self.assertEqual(old_resp.status_code, 401)

        # New password must work
        new_resp = self.client.post(
            "/api/login",
            data=json.dumps({"username": "Admin", "password": "NewSecurePass#2026"}),
            content_type="application/json",
        )
        self.assertEqual(new_resp.status_code, 200)

        # Logout
        self.client.get("/logout")

        # After logout, old password Bill@2026 must STILL fail
        old_resp2 = self.client.post(
            "/api/login",
            data=json.dumps({"username": "Admin", "password": "Bill@2026"}),
            content_type="application/json",
        )
        self.assertEqual(old_resp2.status_code, 401)

        # New password must work again
        new_resp2 = self.client.post(
            "/api/login",
            data=json.dumps({"username": "Admin", "password": "NewSecurePass#2026"}),
            content_type="application/json",
        )
        self.assertEqual(new_resp2.status_code, 200)

    def test_logout(self):
        # Login first
        self.client.post(
            "/api/login",
            data=json.dumps({"username": "Admin", "password": "Bill@2026"}),
            content_type="application/json",
        )
        # Logout
        resp = self.client.get("/logout")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

        # Now accessing / redirects back to /login
        resp_after = self.client.get("/")
        self.assertEqual(resp_after.status_code, 302)
        self.assertIn("/login", resp_after.headers["Location"])


if __name__ == "__main__":
    unittest.main()
