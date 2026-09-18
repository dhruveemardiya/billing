import io
from PIL import Image
import pypdfium2 as pdfium
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

reader = PdfReader('f:/BILLING/project/demo.pdf')
p1 = reader.pages[1]
page_width = float(p1.mediabox.width)
page_height = float(p1.mediabox.height)

# Mask white rects over the 5 values on page 1
buf = io.BytesIO()
c = canvas.Canvas(buf, pagesize=(page_width, page_height))
c.setFillColorRGB(1.0, 1.0, 1.0)

# Coupon fields:
# Group No: 44.9 to 120
# Customer ID: 134.2 to 230
# Due Date: 239.8 to 330
# Amount Upto: 367.8 to 460
# Amount After: 496.2 to 550
coupon_fields = [
    ("DI070010", 44.9, 120.0),
    ("7432005324", 134.2, 230.0),
    ("24/08/2025", 239.8, 330.0),
    ("386.42", 367.8, 460.0),
    ("392.22", 496.2, 550.0),
]

# Erase old static values (top: 819.8 to 827.2)
for text, x0, x1 in coupon_fields:
    y0 = page_height - 827.2
    y1 = page_height - 819.8
    c.rect(x0 - 1.0, y0, (x1 - x0) + 2.0, y1 - y0, stroke=0, fill=1)

# Draw new values
c.setFillColorRGB(0, 0, 0)
c.setFont("Helvetica-Bold", 6.0)
baseline = page_height - 825.6
for text, x0, x1 in coupon_fields:
    c.drawString(x0, baseline, text)

c.save()
buf.seek(0)

overlay_reader = PdfReader(buf)
p1.merge_page(overlay_reader.pages[0])

writer = PdfWriter()
writer.add_page(p1)
out_buf = io.BytesIO()
writer.write(out_buf)
out_buf.seek(0)

doc = pdfium.PdfDocument(out_buf)
page = doc[0]
bmp = page.render(scale=2.0)
img = bmp.to_pil()
# Crop to coupon area (y: 780..840 at scale 2.0 -> y: 1560..1680)
crop = img.crop((0, 1560, int(page_width * 2.0), 1680))
crop.save('f:/BILLING/project/scratch/demo_test_coupon_render.png')
print("Rendered demo_test_coupon_render.png successfully!")
