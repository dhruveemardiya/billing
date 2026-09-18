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
        # Crop to chart region: x ~ 300 to 560, y ~ 570 to 720
        # In pdfplumber, top is ~ 570 to 720
        chart_crop = p.crop((300, 560, 560, 720))
        words = chart_crop.extract_words()
        print("Chart crop words:")
        for w in sorted(words, key=lambda x: (round(x['top'], 1), round(x['x0'], 1))):
            print(f"  {w['text']:10s} at x0={w['x0']:.1f}, top={w['top']:.1f}, bottom={w['bottom']:.1f}, font={w.get('fontname')}")
