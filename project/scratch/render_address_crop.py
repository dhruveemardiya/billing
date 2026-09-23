import pypdfium2 as pdfium

doc = pdfium.PdfDocument("scratch/test_address_demo.pdf")
page = doc[0]
image = page.render(scale=2).to_pil()

# Crop the consumer details panel
# x from 30 to 220 (scale 2 means 60 to 440)
# y from 150 to 240 (scale 2 means 300 to 480)
w, h = image.size
crop_box = (60, 300, 440, 480)
crop = image.crop(crop_box)
crop.save("scratch/address_crop_demo.png")
print("Saved scratch/address_crop_demo.png")
