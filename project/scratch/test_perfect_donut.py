import sys
sys.path.insert(0, 'f:/BILLING/project')

import math, io
from PIL import Image
import pypdfium2 as pdfium
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, NameObject
import font_manager

registered_fonts = font_manager.ensure_template_fonts_registered('f:/BILLING/project/demo.pdf')
font_bold = "NeurialGrotesk-Bold" if "NeurialGrotesk-Bold" in registered_fonts else "Helvetica-Bold"
font_reg = "NeurialGrotesk-Regular" if "NeurialGrotesk-Regular" in registered_fonts else "Helvetica"
rupee_font = "SymbolMT" if "SymbolMT" in registered_fonts else font_bold

# Test strip ops 711..789
reader = PdfReader('f:/BILLING/project/demo.pdf')
p0 = reader.pages[0]
stream = ContentStream(p0.get_contents(), reader)
new_ops = [op for i, op in enumerate(stream.operations) if not (711 <= i <= 789)]
stream.operations = new_ops
p0[NameObject('/Contents')] = stream

page_width = float(p0.mediabox.width)
page_height = float(p0.mediabox.height)

buf = io.BytesIO()
c = canvas.Canvas(buf, pagesize=(page_width, page_height))

energy_amt = 1939.00
fixed_amt = 55.00
fppas_amt = 220.94
total_bill_amt = 2547.18

comp_total = energy_amt + fixed_amt + fppas_amt
fixed_deg = (fixed_amt / comp_total) * 360.0
energy_deg = (energy_amt / comp_total) * 360.0
fppas_deg = (fppas_amt / comp_total) * 360.0

cx = 440.0
cy = page_height - 448.0
R_outer = 53.0
R_inner = 35.0
CREAM_BG = (247 / 255, 242 / 255, 238 / 255)

fixed_start = 315.5
energy_start = fixed_start + fixed_deg
fppas_start = energy_start + energy_deg

slices = [
    {"name": "Fixed charges", "amount": fixed_amt, "start": fixed_start, "extent": fixed_deg, "color": "#CCD1D6"},
    {"name": "Energy charges", "amount": energy_amt, "start": energy_start, "extent": energy_deg, "color": "#1F2327"},
    {"name": "FPPCA charges", "amount": fppas_amt, "start": fppas_start, "extent": fppas_deg, "color": "#5F666D"},
]

# Wedges
for s in slices:
    if s["extent"] > 0.001:
        c.setFillColor(HexColor(s["color"]))
        c.wedge(cx - R_outer, cy - R_outer, cx + R_outer, cy + R_outer, s["start"], s["extent"], stroke=0, fill=1)

# Dividers
c.setStrokeColorRGB(*CREAM_BG)
c.setLineWidth(1.2)
for s in slices:
    rad = math.radians(s["start"])
    c.line(cx + (R_inner - 0.5) * math.cos(rad), cy + (R_inner - 0.5) * math.sin(rad),
           cx + (R_outer + 0.5) * math.cos(rad), cy + (R_outer + 0.5) * math.sin(rad))

# Inner hole
c.setFillColorRGB(*CREAM_BG)
c.circle(cx, cy, R_inner, stroke=0, fill=1)

# Center total
c.setFillColorRGB(0, 0, 0)
c.setFont(rupee_font, 9.0)
c.drawCentredString(cx, cy + 2.5, "₹")
c.setFont(font_bold, 8.5)
c.drawCentredString(cx, cy - 8.0, f"{total_bill_amt:,.2f}")

# Leader lines
c.setStrokeColorRGB(0.2, 0.2, 0.2)
c.setLineWidth(0.4)
ty_energy = page_height - 435.07
c.line(cx - R_outer, ty_energy, 370.0, ty_energy)
ty_fixed = page_height - 449.27
c.line(cx + R_outer, ty_fixed, 510.0, ty_fixed)
ty_fppca = page_height - 498.32
c.line(467.51, ty_fppca, 510.0, ty_fppca)

# Helper to draw rupee amount string
def draw_amt_right(x_right, y, amt):
    amt_str = f"{amt:,.2f}"
    c.setFont(font_bold, 8.0)
    aw = c.stringWidth(amt_str, font_bold, 8.0)
    c.setFont(rupee_font, 8.0)
    rw = c.stringWidth("₹", rupee_font, 8.0)
    total_w = rw + aw
    c.drawString(x_right - total_w, y, "₹")
    c.setFont(font_bold, 8.0)
    c.drawString(x_right - aw, y, amt_str)

def draw_amt_left(x_left, y, amt):
    amt_str = f"{amt:,.2f}"
    c.setFont(rupee_font, 8.0)
    c.drawString(x_left, y, "₹")
    rw = c.stringWidth("₹", rupee_font, 8.0)
    c.setFont(font_bold, 8.0)
    c.drawString(x_left + rw, y, amt_str)

# Energy charges on left (right-aligned to 365)
draw_amt_right(365.0, page_height - 438.0, energy_amt)
c.setFont(font_reg, 7.0)
c.drawRightString(365.0, page_height - 446.5, "Energy")
c.drawRightString(365.0, page_height - 454.5, "Charges")

# Fixed charges on right (left-aligned at 515)
draw_amt_left(515.0, page_height - 439.0, fixed_amt)
c.setFont(font_reg, 7.0)
c.drawString(515.0, page_height - 447.5, "Fixed Charges")

# FPPCA charges on right (left-aligned at 515)
draw_amt_left(515.0, page_height - 501.0, fppas_amt)
c.setFont(font_reg, 7.0)
c.drawString(515.0, page_height - 509.5, "FPPCA Charges")

c.save()
buf.seek(0)
p0.merge_page(PdfReader(buf).pages[0])

writer = PdfWriter()
writer.add_page(p0)
out_buf = io.BytesIO()
writer.write(out_buf)
out_buf.seek(0)

doc = pdfium.PdfDocument(out_buf)
bmp = doc[0].render(scale=2.0)
img = bmp.to_pil()
crop = img.crop((600, 720, 1190, 1080))
crop.save('f:/BILLING/project/scratch/demo_perfect_donut.png')
print("Saved demo_perfect_donut.png successfully!")
