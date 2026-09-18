import pdfplumber
with pdfplumber.open("demo.pdf") as p1, pdfplumber.open("DEMONEWPDF.pdf") as p2:
    t1 = p1.pages[0].extract_text().lower()
    t2 = p2.pages[0].extract_text().lower()
    print("demo has 'ramaji':", "ramaji" in t1, "new has 'ramaji':", "ramaji" in t2)
    print("demo has 'vanakbara':", "vanakbara" in t1, "new has 'vanakbara':", "vanakbara" in t2)
    print("demo has 'diu':", "diu" in t1, "new has 'diu':", "diu" in t2)
    print("demo has 'vadi sheri':", "vadi sheri" in t1, "new has 'vadi sheri':", "vadi sheri" in t2)

