import pypdf

reader = pypdf.PdfReader('demo.pdf')
page = reader.pages[0]

def visitor(text, cm, tm, fontDict, fontSize):
    y_from_top = 841.89 - tm[5]
    x = tm[4]
    if 150 <= y_from_top <= 240 and x < 250:
        print(f"y_from_top={y_from_top:.1f}, x={x:.1f}, text='{text}', size={fontSize}, font={fontDict.get('/BaseFont', '')}")

page.extract_text(visitor_text=visitor)
