import pdfplumber

with pdfplumber.open('f:/BILLING/project/demo.pdf') as pdf:
    p0 = pdf.pages[0]
    words0 = p0.extract_words()
    print("\n--- Headline words on page 0 (top 280-360) ---")
    for w in words0:
        if 280 <= w['top'] <= 360:
            print(f"{w['text']}: x0={w['x0']:.2f}, x1={w['x1']:.2f}, top={w['top']:.2f}, bottom={w['bottom']:.2f}")
