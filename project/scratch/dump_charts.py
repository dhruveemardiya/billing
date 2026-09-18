import pdfplumber

def dump_chart(path):
    print("=" * 60)
    print("FILE:", path)
    with pdfplumber.open(path) as pdf:
        p = pdf.pages[0]
        # Chart bounding box: x0=315, top=580, x1=550, bottom=700
        words = p.crop((315, 580, 550, 700)).extract_words()
        for w in sorted(words, key=lambda x: (round(x['top'], 1), round(x['x0'], 1))):
            font = w.get('fontname', '')
            print(f"  {w['text']:12s} at x0={w['x0']:5.1f}, top={w['top']:5.1f}, font={font}")

dump_chart(r"f:\BILLING\00_Electricity_Bill_June_2025_7432005324.pdf")
dump_chart(r"f:\BILLING\07_Electricity_Bill_August_2026_7432005324.pdf")
