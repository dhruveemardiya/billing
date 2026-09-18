from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, NameObject
import pypdfium2 as pdfium
import io

reader = PdfReader('f:/BILLING/project/demo.pdf')
p0 = reader.pages[0]
stream = ContentStream(p0.get_contents(), reader)
print("Before stripping, ops:", len(stream.operations))

# Keep only ops not in 711..789
new_ops = []
for i, (operands, op) in enumerate(stream.operations):
    if 711 <= i <= 789:
        continue
    new_ops.append((operands, op))

stream.operations = new_ops
p0[NameObject('/Contents')] = stream

writer = PdfWriter()
writer.add_page(p0)
buf = io.BytesIO()
writer.write(buf)
buf.seek(0)

# Render with pypdfium2
pdf = pdfium.PdfDocument(buf)
page = pdf[0]
bmp = page.render(scale=2.0)
img = bmp.to_pil()
crop = img.crop((600, 720, 1190, 1080))
crop.save('f:/BILLING/project/scratch/demo_stripped_donut.png')
print("Saved stripped donut crop successfully!")
