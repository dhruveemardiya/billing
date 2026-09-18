import pdfplumber

with pdfplumber.open(r"f:\BILLING\project\DEMONEWPDF.pdf") as pdf:
    p1 = pdf.pages[1]
    words = [w for w in p1.extract_words() if w["top"] >= 780]
    words.sort(key=lambda w: (round(w["top"], 1), round(w["x0"], 1)))
    print("Words on Page 1 of DEMONEWPDF.pdf (bottom area, y >= 780):")
    for w in words:
        print(f"  {w['text']:25s} x0={w['x0']:.2f}, top={w['top']:.2f}, x1={w['x1']:.2f}, bottom={w['bottom']:.2f}")
