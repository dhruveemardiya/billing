import pdfplumber

with pdfplumber.open(r"f:\BILLING\project\demo.pdf") as pdf:
    for p_idx, page in enumerate(pdf.pages):
        for line in page.extract_text().split("\n"):
            if "amount after" in line.lower() or "amount upto" in line.lower() or "due date" in line.lower():
                print(f"Page {p_idx}: {line}")
