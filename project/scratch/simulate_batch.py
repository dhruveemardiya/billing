import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from direct_bill_service import process_direct_bill

form_data = {
    "customer_id": "7432005324",
    "consumer_name": "BHAVNABEN MAHESHKUMAR TRIVEDI",
    "address": "House No 399, Vadi Sheri, Vanakbara, Diu",
    "mobile_no": "9876543210",
    "email": "bhavna@gmail.com",
    "category": "Residential",
    "billing_cycle": "Bi-Monthly",
    "start_month": "June 2025",
    "end_month": "August 2026",
    "start_reading": 1000,
    "reference_units": 100,
}

res = process_direct_bill(form_data)
print("Batch processed. Total bills:", len(res["bills"]))

for b in res["bills"]:
    idx = b["index"]
    m = b["billing_month"]
    c = b["consumer"]
    print(f"\nBill {idx}: {m}")
    print(f"  units: {c['units']}")
    print(f"  chart_months: {c['chart_month_labels']}")
    print(f"  chart_years:  {c['chart_year_labels']}")
    print(f"  chart_values: {c['chart_values']}")
