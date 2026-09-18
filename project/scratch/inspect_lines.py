import pdfplumber

with pdfplumber.open('f:/BILLING/project/demo.pdf') as pdf:
    p0 = pdf.pages[0]
    # Check lines and curves
    print("--- Curves/Lines on p0 around donut ---")
    for curve in p0.curves:
        if 350 <= curve['top'] <= 550 and curve['x0'] >= 300:
            print("Curve:", curve['x0'], curve['top'], curve['x1'], curve['bottom'])
    for line in p0.lines:
        if 350 <= line['top'] <= 550 and line['x0'] >= 300:
            print("Line:", line['x0'], line['top'], line['x1'], line['bottom'], line.get('pts'))
    for rect in p0.rects:
        if 350 <= rect['top'] <= 550 and rect['x0'] >= 300:
            print("Rect:", rect['x0'], rect['top'], rect['x1'], rect['bottom'])
