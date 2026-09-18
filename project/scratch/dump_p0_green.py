import pypdf

reader = pypdf.PdfReader(r"f:\BILLING\07_Electricity_Bill_August_2026_7432005324.pdf")
print("Number of pages:", len(reader.pages))
p0 = reader.pages[0]
print(p0.extract_text().encode("ascii", "replace").decode("ascii"))
