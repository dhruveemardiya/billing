import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from direct_bill_service import process_direct_bill

form_data_single = {
    "customer_id": "7432005324",
    "consumer_name": "BHAVNABEN MAHESHKUMAR TRIVEDI",
    "address": "House No 399, Vadi Sheri, Vanakbara, Diu",
    "mobile_no": "9876543210",
    "email": "bhavna@gmail.com",
    "category": "Residential",
    "billing_cycle": "Bi-Monthly",
    "start_month": "June 2025",
    "end_month": "June 2025",
    "start_reading": 1000,
    "reference_units": 100,
}

res = process_direct_bill(form_data_single)
b0 = res["bills"][0]
c = b0["consumer"]
print("Single bill June 2025:")
print("  units:", c["units"])
print("  chart_months:", c["chart_month_labels"])
print("  chart_years:", c["chart_year_labels"])
print("  chart_values:", c["chart_values"])
