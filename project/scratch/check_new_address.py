import pypdf

reader = pypdf.PdfReader('DEMONEWPDF.pdf')
page = reader.pages[0]

def visitor(text, cm, tm, fontDict, fontSize):
    y_from_top = 841.89 - tm[5]
    x = tm[4]
    if 160 <= y_from_top <= 280 and x < 230:
        if text.strip():
            print(f"y={y_from_top:.1f}, x={x:.1f}, text='{text.strip()}', size={fontSize}")

page.extract_text(visitor_text=visitor)
