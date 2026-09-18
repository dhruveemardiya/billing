import glob
import os
import sys
sys.path.insert(0, ".")
import config
import pdfplumber

files = [f for f in glob.glob(os.path.join(config.OUTPUT_FOLDER, "direct_*", "*7432005324*.pdf")) if "Electricity_Bill" in f]
# Find the latest direct_* folder
folders = sorted(set(os.path.dirname(f) for f in files), key=os.path.getmtime)
latest_folder = folders[-1]
print("Latest folder:", latest_folder)

batch_files = sorted(glob.glob(os.path.join(latest_folder, "*.pdf")))
print("Batch bills count:", len(batch_files))

for bf in batch_files:
    with pdfplumber.open(bf) as pdf:
        text = pdf.pages[0].extract_text()
        lines = text.splitlines()
        # Find billing month and units
        b_month = ""
        units = ""
        for i, line in enumerate(lines):
            if "BILLING MONTH" in line:
                b_month = lines[i+1] if i+1 < len(lines) else ""
            if "Units Billed" in line or "UNITS BILLED" in line:
                units = line
        print(f"{os.path.basename(bf)}:")
        for line in lines:
            if "Residential" in line:
                print("   ", line)
            if "kWh" in line or "Units" in line:
                print("   ", line)
