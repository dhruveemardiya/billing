import os, time, pypdf

for path in [r"f:\BILLING\00_Electricity_Bill_June_2025_7432005324.pdf", r"f:\BILLING\07_Electricity_Bill_August_2026_7432005324.pdf"]:
    print("=== File:", path)
    stat = os.stat(path)
    print("  mtime:", time.ctime(stat.st_mtime))
    print("  ctime:", time.ctime(stat.st_ctime))
    print("  size:", stat.st_size)
    reader = pypdf.PdfReader(path)
    print("  meta:", reader.metadata)
