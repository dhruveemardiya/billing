import pypdfium2 as pdfium
from PIL import Image

pdf = pdfium.PdfDocument('f:/BILLING/project/demo.pdf')
page = pdf[0]
bitmap = page.render(scale=2.0)
img = bitmap.to_pil()

# Crop to donut area:
# In 72 dpi: x: 300 to 595, y: 360 to 540
# Scale 2.0: x: 600 to 1190, y: 720 to 1080
donut_crop = img.crop((600, 720, 1190, 1080))
donut_crop.save('f:/BILLING/project/scratch/demo_pdf_donut.png')

# Also crop coupon area on page 1:
# Page 1: x: 0 to 595, y: 780 to 842
p1 = pdf[1]
b1 = p1.render(scale=2.0)
img1 = b1.to_pil()
coupon_crop = img1.crop((0, 1550, 1190, 1684))
coupon_crop.save('f:/BILLING/project/scratch/demo_pdf_coupon.png')

# Also crop sub-station area on page 0:
# x: 400 to 595, y: 220 to 270
# Scale 2.0: x: 800 to 1190, y: 440 to 540
substation_crop = img.crop((800, 440, 1190, 540))
substation_crop.save('f:/BILLING/project/scratch/demo_pdf_substation.png')

print("Saved crops successfully!")
