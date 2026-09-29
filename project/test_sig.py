from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import pypdfium2 as pdfium

pdfmetrics.registerFont(TTFont('Shruti-Bold', 'C:/Windows/Fonts/shrutib.ttf'))

scale = 595.0 / 975.0
page_h = 1280.0 * scale

c = canvas.Canvas('test_sig2.pdf', pagesize=(595, page_h))
# Draw box: x=680..901, y=1036..1091
x0, y0, w, h = 680 * scale, page_h - 1091 * scale, (901 - 680) * scale, (1091 - 1036) * scale
c.rect(x0, y0, w, h, stroke=1, fill=0)

# Text: •ભૂલચૂક લેવી દેવી at top
c.setFont('Shruti-Bold', 7.8)
c.setFillColorRGB(0.1, 0.12, 0.15)
c.drawString(688 * scale, page_h - 1050 * scale, '•ભૂલચૂક લેવી દેવી')

# Text: Junior Asst.'s Sign at bottom right
c.setFont('Helvetica-Bold', 8.2)
c.drawString(775 * scale, page_h - 1082 * scale, "Junior Asst.'s Sign")

# Signature loop in blue ink matching user image 1:
c.saveState()
c.setStrokeColorRGB(0.08, 0.13, 0.45)
c.setLineWidth(1.3)
c.setLineCap(1)
c.setLineJoin(1)

def pt(px, py):
    return px * scale, page_h - py * scale

path = c.beginPath()
path.moveTo(*pt(805, 1073))
path.curveTo(*pt(820, 1058), *pt(835, 1045), *pt(848, 1045))
path.curveTo(*pt(862, 1045), *pt(872, 1062), *pt(868, 1075))
path.curveTo(*pt(862, 1088), *pt(842, 1088), *pt(836, 1075))
path.curveTo(*pt(832, 1060), *pt(850, 1055), *pt(865, 1062))
c.drawPath(path, stroke=1, fill=0)
c.restoreState()

c.save()
doc = pdfium.PdfDocument('test_sig2.pdf')
img = doc[0].render(scale=3.0).to_pil()
crop = img.crop((int(675 * scale * 3.0), int(1030 * scale * 3.0), int(906 * scale * 3.0), int(1096 * scale * 3.0)))
crop.save('test_sig_box.png')
print('Saved test_sig_box.png')
