import pdfplumber

with pdfplumber.open(r"f:\BILLING\00_Electricity_Bill_June_2025_7432005324.pdf") as pdf:
    p1 = pdf.pages[1]
    print("Words in bottom region of 00_Electricity_Bill_June_2025_7432005324.pdf (y >= 750):")
    for w in sorted([w for w in p1.extract_words() if w["top"] >= 750], key=lambda w: (round(w["top"], 1), round(w["x0"], 1))):
        print(f"  {w['text']:25s} x0={w['x0']:.2f}, top={w['top']:.2f}, x1={w['x1']:.2f}, bottom={w['bottom']:.2f}")
