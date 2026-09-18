import os, pdfplumber

folder = r"C:\Users\91798\AppData\Local\Temp\electricity_bill_generator\output\direct_6e4a3f033e"
files = sorted([f for f in os.listdir(folder) if f.endswith(".pdf")])

for fname in files:
    fpath = os.path.join(folder, fname)
    with pdfplumber.open(fpath) as pdf:
        p0 = pdf.pages[0]
        # Chart words
        chart_words = [w for w in p0.extract_words() if 300 <= w["x0"] <= 560 and 560 <= w["top"] <= 720]
        chart_words.sort(key=lambda w: (round(w["top"], 1), round(w["x0"], 1)))
        
        # In our overlay:
        # Month labels are at top ~ 689-696
        # Year labels are at top ~ 681-687
        # Numbers are at top ~ 600-660
        months = [w["text"] for w in chart_words if 688 <= w["top"] <= 697]
        years = [w["text"] for w in chart_words if 681 <= w["top"] <= 687]
        print(f"\n{fname}:")
        print("  Months:", months)
        print("  Years:", years)
