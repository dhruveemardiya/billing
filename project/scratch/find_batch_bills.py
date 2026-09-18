import glob
import os
import sys
sys.path.insert(0, ".")
import config
import pdfplumber

files = glob.glob(os.path.join(config.OUTPUT_FOLDER, "direct_*", "*7432005324*.pdf"))
print("Found bills for 7432005324:", len(files))
for f in sorted(files):
    with pdfplumber.open(f) as pdf:
        text = pdf.pages[0].extract_text()
        month = ""
        units = ""
        for line in text.splitlines():
            if "BILLING MONTH" in line or "Billing Month" in line:
                pass
            if "Residential" in line or "Commercial" in line:
                print("Line:", line)
