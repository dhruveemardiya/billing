import pdfplumber

def check_chart(path):
    print("=" * 60)
    print("PDF:", path)
    with pdfplumber.open(path) as pdf:
        p0 = pdf.pages[0]
        chart_words = [w for w in p0.extract_words() if 300 <= w["x0"] <= 560 and 560 <= w["top"] <= 720]
        chart_words.sort(key=lambda w: (round(w["top"], 1), round(w["x0"], 1)))
        print(f"Total chart words: {len(chart_words)}")
        for w in chart_words:
            print(f"  {w['text']:12s} x0={w['x0']:.1f}, top={w['top']:.1f}, x1={w['x1']:.1f}, bottom={w['bottom']:.1f}")

check_chart(r"f:\BILLING\00_Electricity_Bill_June_2025_7432005324.pdf")
check_chart(r"f:\BILLING\07_Electricity_Bill_August_2026_7432005324.pdf")
