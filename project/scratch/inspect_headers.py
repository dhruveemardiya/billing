import pdfplumber

files = [
    r"f:\BILLING\00_Electricity_Bill_June_2025_7432005324.pdf",
    r"f:\BILLING\07_Electricity_Bill_August_2026_7432005324.pdf"
]

for f in files:
    print("=" * 60)
    print("FILE:", f)
    with pdfplumber.open(f) as pdf:
        p = pdf.pages[0]
        text = p.extract_text()
        for line in text.splitlines()[:25]:
            print("  ", line)
