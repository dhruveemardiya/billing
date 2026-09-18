import sys, os
sys.path.insert(0, 'f:/BILLING/project')

import pypdfium2 as pdfium
import direct_bill_service

payload = {
    "customer_id": "7432005324",
    "consumer_name": "TEST CONSUMER",
    "address": "123 Test Street, City",
    "mobile_no": "9876543210",
    "email": "test@example.com",
    "category": "Residential",
    "billing_cycle": "Monthly",
    "start_month": "June 2025",
    "end_month": "June 2025",
    "start_reading": 1000,
    "reference_units": 700,
}

res = direct_bill_service.process_direct_bill(payload)
print("Success:", res["success"])
pdf_path = res["bills"][0]["output_path"]
print("Generated PDF:", pdf_path)

doc = pdfium.PdfDocument(pdf_path)
print("Pages:", len(doc))
p0 = doc[0]
bmp0 = p0.render(scale=2.0)
img0 = bmp0.to_pil()

# Save headline area crop: x: 30..300, y: 280..370
crop_headline = img0.crop((60, 560, 600, 740))
crop_headline.save("f:/BILLING/project/scratch/current_headline_crop.png")

# Save substation area crop: x: 400..590, y: 220..270
crop_substation = img0.crop((800, 440, 1180, 540))
crop_substation.save("f:/BILLING/project/scratch/current_substation_crop.png")

# Save page 1 coupon crop: x: 0..595, y: 780..842
p1 = doc[1]
bmp1 = p1.render(scale=2.0)
img1 = bmp1.to_pil()
crop_coupon = img1.crop((0, 1560, 1190, 1684))
crop_coupon.save("f:/BILLING/project/scratch/current_coupon_crop.png")

# Save page 0 donut crop
crop_donut = img0.crop((600, 720, 1190, 1080))
crop_donut.save("f:/BILLING/project/scratch/current_donut_crop.png")

print("Saved all crops successfully!")
