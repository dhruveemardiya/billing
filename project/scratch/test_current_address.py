import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pypdf
import billing_engine
import pdf_generator
import template_detector
import pdf_mapper

addr = "Building no.7, 404, Anandnagar flats, behind shell petrol pump, Prahlad Nagar, Ahmedabad, Gujarat"

consumer = {
    "customer_id": "743200550",
    "consumer_name": "DHRUVI",
    "address": addr,
    "area": "DIU",
    "t_no": "3004645778",
    "billing_mode": "30 days",
    "legacy_no": "200550",
    "bill_no": "214004095971",
    "category": "Residential",
    "billing_month": "June 2026",
    "reading_date": "02/06/2026",
    "bill_date": "10/06/2026",
    "due_date": "25/06/2026",
    "units": 89,
    "meter_no": "DND52642",
    "start_reading": 1000,
    "end_reading": 1089,
    "previous_payment": 200.0,
    "previous_payment_date": "20/05/2026"
}

# Test with demo.pdf
ts = template_detector.detect_template_structure('demo.pdf')
bill = billing_engine.compute_bill(consumer)
out = "scratch/test_address_demo.pdf"
pdf_generator.generate_bill_pdf('demo.pdf', consumer, bill, out, template_structure=ts)

reader = pypdf.PdfReader(out)
p0 = reader.pages[0].extract_text()
print("=== Extracted text from demo.pdf ===")
for line in p0.splitlines():
    if any(k in line.upper() for k in ["DHRUVI", "BUILDING", "404", "ANANDNAGAR", "SHELL", "PRAHLAD", "AHMEDABAD", "GUJARAT"]):
        print("  ", line)

# Test with DEMONEWPDF.pdf
ts_new = template_detector.detect_template_structure('DEMONEWPDF.pdf')
out_new = "scratch/test_address_new.pdf"
pdf_generator.generate_bill_pdf('DEMONEWPDF.pdf', consumer, bill, out_new, template_structure=ts_new)

reader_new = pypdf.PdfReader(out_new)
p0_new = reader_new.pages[0].extract_text()
print("=== Extracted text from DEMONEWPDF.pdf ===")
for line in p0_new.splitlines():
    if any(k in line.upper() for k in ["DHRUVI", "BUILDING", "404", "ANANDNAGAR", "SHELL", "PRAHLAD", "AHMEDABAD", "GUJARAT"]):
        print("  ", line)
