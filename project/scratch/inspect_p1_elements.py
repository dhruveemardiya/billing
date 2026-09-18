import pdfplumber

with pdfplumber.open(r"f:\BILLING\project\demo.pdf") as pdf:
    p1 = pdf.pages[1]
    # Check images or drawings (like barcode)
    print("Curves/Lines/Images in bottom region (y >= 750):")
    for img in p1.images:
        print("  Image:", img)
    for rect in [r for r in p1.rects if r["top"] >= 750]:
        print("  Rect:", rect["x0"], rect["top"], rect["x1"], rect["bottom"], rect.get("fill"))
    for line in [l for l in p1.lines if l["top"] >= 750]:
        print("  Line:", line["x0"], line["top"], line["x1"], line["bottom"])
    
    print("\nWords in bottom region (y >= 750):")
    for w in sorted([w for w in p1.extract_words() if w["top"] >= 750], key=lambda w: (round(w["top"], 1), round(w["x0"], 1))):
        print(f"  {w['text']:25s} x0={w['x0']:.2f}, top={w['top']:.2f}, x1={w['x1']:.2f}, bottom={w['bottom']:.2f}")
