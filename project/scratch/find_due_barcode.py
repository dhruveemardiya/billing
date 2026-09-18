import pdfplumber

with pdfplumber.open(r"f:\BILLING\project\demo.pdf") as pdf:
    for p_idx, page in enumerate(pdf.pages):
        print(f"=== PAGE {p_idx} ===")
        for w in page.extract_words():
            if any(k in w["text"].lower() for k in ["due", "upto", "after", "barcode", "743200550"]):
                print(f"  {w['text']:25s} page={p_idx}, x0={w['x0']:.2f}, top={w['top']:.2f}, bottom={w['bottom']:.2f}")
