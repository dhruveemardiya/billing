import pypdfium2 as pdfium

def render_chart_crop(pdf_path, out_png):
    doc = pdfium.PdfDocument(pdf_path)
    page = doc[0]
    # Page size in points: ~ 595 x 842
    # Chart region: x0=300, top=550, x1=560, bottom=710
    # In pdfium, coordinate origin is bottom-left
    # 842 - 710 = 132 (bottom), 842 - 550 = 292 (top)
    w, h = page.get_size()
    scale = 2.0  # 144 dpi
    bitmap = page.render(scale=scale)
    img = bitmap.to_pil()
    
    # Crop to chart region (scaled by 2)
    crop_box = (int(300 * scale), int(550 * scale), int(560 * scale), int(715 * scale))
    cropped = img.crop(crop_box)
    cropped.save(out_png)
    print("Saved:", out_png)

render_chart_crop(r"f:\BILLING\00_Electricity_Bill_June_2025_7432005324.pdf", "scratch/user_june_2025_old.png")
render_chart_crop(r"f:\BILLING\07_Electricity_Bill_August_2026_7432005324.pdf", "scratch/user_aug_2026_green.png")
