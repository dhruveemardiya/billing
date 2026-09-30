import unittest
from app import app

class TestBillTypeUI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess["authenticated"] = True
            sess["user"] = "Admin"

    def test_default_state_and_cards(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # 1. Torrent Bill is default checked
        self.assertIn('id="bill_type_torrent" value="Torrent Bill" class="bill-type-radio-input" checked', html)

        # 2. Both cards exist
        self.assertIn('id="bill-type-torrent-card"', html)
        self.assertIn('id="bill-type-pgvcl-card"', html)

        # 3. Logos with title attributes
        self.assertIn('title="PGVCL Official Logo"', html)
        self.assertIn('title="Torrent Power Logo"', html)

        # 4. Config identifiers
        self.assertIn('id="torrent-config-section"', html)
        self.assertIn('id="pgvcl-config-section"', html)

        # 5. Blue theme CSS for PGVCL selected state
        self.assertIn('.bill-type-card.pgvcl.selected', html)
        self.assertIn('#2563eb', html)

    def test_conditional_sections_and_fields(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # PGVCL section has default display: none on initial load
        self.assertIn('id="pgvcl-config-section" class="provider-specific-section pgvcl-only-section" style="display: none;"', html)
        # Torrent Bill requires only standard common fields (no extra section shown)
        self.assertIn('id="torrent-config-section" style="display:none;"', html)
        self.assertNotIn('Torrent Power Supply & Metering', html)

        # Redundant badges are completely removed
        self.assertNotIn('PGVCL Specific', html)
        self.assertNotIn('PGVCL Consumer No', html)

        # Subtle blue styling for PGVCL section exists
        self.assertIn('#pgvcl-config-section .form-section-card', html)
        self.assertIn('linear-gradient(180deg, #f8faff 0%, #f0f6ff 100%)', html)

        # PGVCL-specific fields exist inside pgvcl-config-section without redundant badges
        self.assertIn('id="direct_village_name"', html)
        self.assertIn('id="direct_village"', html)
        self.assertIn('id="direct_taluka"', html)
        self.assertIn('id="direct_district"', html)

        # Common fields exist for both providers
        self.assertIn('id="direct_customer_id"', html)
        self.assertIn('id="direct_consumer_name"', html)
        self.assertIn('id="direct_address"', html)
        self.assertIn('id="direct_mobile_no"', html)
        self.assertIn('id="direct_email"', html)
        self.assertIn('id="direct_category"', html)
        self.assertIn('id="direct_billing_cycle"', html)
        self.assertIn('id="direct_start_month"', html)
        self.assertIn('id="direct_end_month"', html)
        self.assertIn('id="direct_start_reading"', html)
        self.assertIn('id="direct_units"', html)

    def test_conditional_javascript_logic(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # Function definition and execution on DOM load
        self.assertIn("function updateBillTypeConditionalFields(billType)", html)
        self.assertIn("updateBillTypeConditionalFields(initialCheckedBillType)", html)
        self.assertIn("updateBillTypeConditionalFields(radio.value)", html)

        # Dynamic placeholder and label updates
        self.assertIn('Consumer No', html)
        self.assertIn('Customer ID', html)
        self.assertIn('e.g. 01234567890', html)
        self.assertIn('e.g. 743200550', html)

        # Disabling inputs so hidden fields are not required and not sent
        self.assertIn('el.disabled = true;', html)
        self.assertIn('el.required = false;', html)
        self.assertIn('el.disabled = false;', html)

    def test_direct_bill_generation_torrent_flow(self):
        """Test generating a Torrent Bill without any PGVCL location fields."""
        payload = {
            "bill_type": "Torrent Bill",
            "customer_id": "743200550",
            "consumer_name": "Torrent Test Consumer",
            "address": "402 Riverfront Heights, Ashram Road, Ahmedabad",
            "mobile_no": "9825012345",
            "email": "torrent.user@example.com",
            "category": "Residential",
            "billing_cycle": "Bi-Monthly",
            "start_month": "June 2025",
            "end_month": "June 2025",
            "start_reading": 5000,
            "reference_units": 600,
        }
        resp = self.client.post("/api/generate-bill-direct", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("bill_type"), "Torrent Bill")

    def test_direct_bill_generation_pgvcl_flow(self):
        """Test generating a PGVCL Bill with PGVCL location fields."""
        payload = {
            "bill_type": "PGVCL Bill",
            "customer_id": "01234567890",
            "consumer_name": "PGVCL Test Consumer",
            "address": "Opposite Bus Station, Veraval",
            "mobile_no": "9825098765",
            "email": "pgvcl.user@example.com",
            "category": "Residential",
            "billing_cycle": "Bi-Monthly",
            "start_month": "June 2025",
            "end_month": "June 2025",
            "start_reading": 3000,
            "reference_units": 450,
            "village_name": "VERAVAL",
            "village": "Veraval (M+OG) V",
            "taluka": "Veraval",
            "district": "GIR SOMNATH",
        }
        resp = self.client.post("/api/generate-bill-direct", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("bill_type"), "PGVCL Bill")
    def test_provider_section_themes(self):
        """Verify provider-specific theme colors and dynamic section classes."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)

        # 1. Section cards have explicit IDs and direct-bill-section has initial theme class
        self.assertIn('id="direct-bill-section" class="theme-torrent"', html)
        self.assertIn('id="consumer-info-section"', html)
        self.assertIn('id="pgvcl-config-section"', html)
        self.assertIn('id="billing-period-section"', html)
        self.assertIn('id="meter-consumption-section"', html)
        self.assertIn('id="direct-result-card"', html)

        # 2. PGVCL Blue Theme CSS rules exist for entire sections
        self.assertIn('#direct-bill-section.theme-pgvcl .form-section-card:not(.bill-type-section-card)', html)
        self.assertIn('.bill-result-card.theme-pgvcl', html)
        self.assertIn('#direct-bill-section.theme-pgvcl .derived-reading-card', html)
        self.assertIn('#direct-bill-section.theme-pgvcl .btn-generate', html)

        # 3. Torrent Green Theme CSS rules exist for entire sections
        self.assertIn('#direct-bill-section.theme-torrent .form-section-card:not(.bill-type-section-card)', html)
        self.assertIn('.bill-result-card.theme-torrent', html)
        self.assertIn('#direct-bill-section.theme-torrent .derived-reading-card', html)
        self.assertIn('#direct-bill-section.theme-torrent .btn-generate', html)

        # 4. Dynamic theme toggling inside JavaScript
        self.assertIn('directBillSection.classList.add("theme-pgvcl")', html)
        self.assertIn('directBillSection.classList.add("theme-torrent")', html)
        self.assertIn('directResultCard.classList.add("theme-pgvcl")', html)
        self.assertIn('directResultCard.classList.add("theme-torrent")', html)

if __name__ == '__main__':
    unittest.main()

