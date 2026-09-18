import pdfplumber

def check_pdf(path):
    print("=" * 60)
    print("PDF:", path)
    with pdfplumber.open(path) as pdf:
        p0 = pdf.pages[0]
        text = p0.extract_text()
        for line in text.split("\n"):
            if any(k in line.lower() for k in ["units", "bill date", "due by", "reading date", "consumption", "customer id", "billing month"]):
                print("  LINE:", line)
        print("\n--- Words in chart region (x: 300 to 560, y: 560 to 720) ---")
        chart_words = [w for w in p0.extract_words() if 300 <= w["x0"] <= 560 and 560 <= w["top"] <= 720]
        chart_words.sort(key=lambda w: (round(w["top"], 1), round(w["x0"], 1)))
        for w in chart_words:
            print(f"  {w['text']:10s} x0={w['x0']:.1f}, top={w['top']:.1f}, x1={w['x1']:.1f}, bottom={w['bottom']:.1f}, font={w.get('fontname')}")

check_pdf(r"f:\BILLING\00_Electricity_Bill_June_2025_7432005324.pdf")
check_pdf(r"f:\BILLING\07_Electricity_Bill_August_2026_7432005324.pdf")
