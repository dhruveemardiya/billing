import pdfplumber

with pdfplumber.open('f:/BILLING/project/demo.pdf') as pdf:
    p1 = pdf.pages[1]
    words = p1.extract_words()
    print("--- Words on page 1 with top > 790 ---")
    for w in words:
        if w['top'] > 790:
            print(f"{w['text']}: x0={w['x0']:.2f}, x1={w['x1']:.2f}, top={w['top']:.2f}, bottom={w['bottom']:.2f}")

    p0 = pdf.pages[0]
    words0 = p0.extract_words()
    print("\n--- Sub-station words on page 0 ---")
    for w in words0:
        if 'station' in w['text'].lower() or 'sub' in w['text'].lower() or 'malala' in w['text'].lower() or (240 <= w['top'] <= 260 and w['x0'] > 400):
            print(f"{w['text']}: x0={w['x0']:.2f}, x1={w['x1']:.2f}, top={w['top']:.2f}, bottom={w['bottom']:.2f}")

    print("\n--- Donut words on page 0 (top 380-530, x0 > 300) ---")
    for w in words0:
        if 380 <= w['top'] <= 530 and w['x0'] >= 300:
            print(f"{w['text']}: x0={w['x0']:.2f}, x1={w['x1']:.2f}, top={w['top']:.2f}, bottom={w['bottom']:.2f}")
