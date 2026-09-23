import pdfplumber

with pdfplumber.open('demo.pdf') as pdf:
    words = pdf.pages[0].extract_words()
    target = [w for w in words if 220 <= w['top'] <= 340 and w['x0'] < 200]
    print(f"Total words found between top 220 and 340: {len(target)}")
    for w in sorted(target, key=lambda x: (round(x['top'], 1), x['x0'])):
        print(f"{w['text']:<25} top={w['top']:.2f}, bottom={w['bottom']:.2f}, x0={w['x0']:.2f}, x1={w['x1']:.2f}")

print("\n--- DEMONEWPDF.pdf ---")
with pdfplumber.open('DEMONEWPDF.pdf') as pdf:
    words = pdf.pages[0].extract_words()
    target = [w for w in words if 240 <= w['top'] <= 340 and w['x0'] < 220]
    print(f"Total words found between top 240 and 340: {len(target)}")
    for w in sorted(target, key=lambda x: (round(x['top'], 1), x['x0'])):
        print(f"{w['text']:<25} top={w['top']:.2f}, bottom={w['bottom']:.2f}, x0={w['x0']:.2f}, x1={w['x1']:.2f}")
