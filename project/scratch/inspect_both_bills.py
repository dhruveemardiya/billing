import pdfplumber

def inspect_bill(path):
    print("=" * 60)
    print("Inspecting:", path)
    with pdfplumber.open(path) as pdf:
        p = pdf.pages[0]
        # Billed units
        for w in p.extract_words():
            if "unit" in w["text"].lower() or "kwh" in w["text"].lower():
                print("  Unit word:", w)
        
        # Chart crop
        crop = p.crop((300, 560, 560, 715))
        words = crop.extract_words()
        print("  Chart elements count:", len(words))
        lines = {}
        for w in words:
            y = round(w["top"], 0)
            lines.setdefault(y, []).append(w["text"])
        for y in sorted(lines.keys()):
            print(f"  y={y:5.0f}: {' '.join(lines[y])}")

inspect_bill(r"f:\BILLING\00_Electricity_Bill_June_2025_7432005324.pdf")
inspect_bill(r"f:\BILLING\07_Electricity_Bill_August_2026_7432005324.pdf")
