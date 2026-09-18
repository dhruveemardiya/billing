import pdfplumber
with pdfplumber.open("DEMONEWPDF.pdf") as pdf:
    p = pdf.pages[0]
    crop = p.crop((300, 500, 560, 715))
    words = crop.extract_words()
    print("Words in DEMONEWPDF.pdf around chart:")
    for w in sorted(words, key=lambda x: (round(x['top'], 1), round(x['x0'], 1))):
        print(f"  {w['text']:15s} top={w['top']:.2f}, bottom={w['bottom']:.2f}, x0={w['x0']:.2f}, x1={w['x1']:.2f}")
