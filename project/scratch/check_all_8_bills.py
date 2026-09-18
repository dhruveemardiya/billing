import os, pdfplumber

folder = r"C:\Users\91798\AppData\Local\Temp\electricity_bill_generator\output\direct_6e4a3f033e"
files = sorted([f for f in os.listdir(folder) if f.endswith(".pdf")])

for fname in files:
    fpath = os.path.join(folder, fname)
    with pdfplumber.open(fpath) as pdf:
        p0 = pdf.pages[0]
        # Look for consumption units
        text = p0.extract_text()
        units_line = [line for line in text.split("\n") if "consumption" in line.lower() or "units" in line.lower()][:2]
        print(f"\n=== {fname} ===")
        print(" ", units_line)
        # Chart words
        chart_words = [w for w in p0.extract_words() if 300 <= w["x0"] <= 560 and 560 <= w["top"] <= 720]
        chart_words.sort(key=lambda w: (round(w["top"], 1), round(w["x0"], 1)))
        # Filter numbers that look like chart bar values (between top 600 and 675)
        bar_vals = [w["text"] for w in chart_words if 600 <= w["top"] <= 665]
        month_words = [w["text"] for w in chart_words if 688 <= w["top"] <= 700]
        year_words = [w["text"] for w in chart_words if 675 <= w["top"] <= 688]
        print("  Bar values extracted:", bar_vals)
        print("  Years:", year_words)
        print("  Months:", month_words)
