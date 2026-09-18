import pdfplumber

with pdfplumber.open('f:/BILLING/project/demo.pdf') as pdf:
    p1 = pdf.pages[1]
    for img in p1.images:
        print("Image on p1:", img['x0'], img['top'], img['x1'], img['bottom'])
    for rect in p1.rects:
        if 750 <= rect['top'] <= 840:
            print("Rect on p1:", rect['x0'], rect['top'], rect['x1'], rect['bottom'])
