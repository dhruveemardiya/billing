import pdfplumber

with pdfplumber.open(r"f:\BILLING\project\DEMONEWPDF.pdf") as pdf:
    p0 = pdf.pages[0]
    chart_words = [w for w in p0.extract_words() if 300 <= w["x0"] <= 560 and 560 <= w["top"] <= 720]
    print(f"Total words in DEMONEWPDF.pdf chart region: {len(chart_words)}")
    for w in chart_words:
        print(f"  {w['text']:10s} x0={w['x0']:.2f}, top={w['top']:.2f}, x1={w['x1']:.2f}, bottom={w['bottom']:.2f}")
