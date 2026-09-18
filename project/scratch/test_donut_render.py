import math
import io
from PIL import Image
import pypdfium2 as pdfium
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, NameObject

# 1. Strip ops 711..789 from page 0 of demo.pdf
reader = PdfReader('f:/BILLING/project/demo.pdf')
p0 = reader.pages[0]
stream = ContentStream(p0.get_contents(), reader)
new_ops = []
for i, (operands, op) in enumerate(stream.operations):
    if 711 <= i <= 789:
        continue
    new_ops.append((operands, op))
stream.operations = new_ops
p0[NameObject('/Contents')] = stream

# 2. Draw dynamic donut overlay
page_width = float(p0.mediabox.width)
page_height = float(p0.mediabox.height)

buf = io.BytesIO()
c = canvas.Canvas(buf, pagesize=(page_width, page_height))

# Values from user bill
energy_amt = 247.50
fixed_amt = 55.00
fppas_amt = 33.52
total_bill_amt = 386.42

comp_total = energy_amt + fixed_amt + fppas_amt
fixed_deg = (fixed_amt / comp_total) * 360.0
energy_deg = (energy_amt / comp_total) * 360.0
fppas_deg = (fppas_amt / comp_total) * 360.0

cx = 440.0
cy = page_height - 448.0 # 394.0
R_outer = 53.0
R_inner = 35.0
CREAM_BG = (247 / 255, 242 / 255, 238 / 255)

# In demo.pdf:
# Fixed charges starts around 315.5 deg
fixed_start = 315.5
energy_start = fixed_start + fixed_deg
fppas_start = energy_start + energy_deg

slices = [
    {"name": "Fixed charges", "amount": fixed_amt, "start": fixed_start, "extent": fixed_deg, "color": "#CCD1D6"},
    {"name": "Energy charges", "amount": energy_amt, "start": energy_start, "extent": energy_deg, "color": "#1F2327"},
    {"name": "FPPCA charges", "amount": fppas_amt, "start": fppas_start, "extent": fppas_deg, "color": "#5F666D"},
]

# Draw wedges
for s in slices:
    if s["extent"] > 0.001:
        c.setFillColor(HexColor(s["color"]))
        c.wedge(cx - R_outer, cy - R_outer, cx + R_outer, cy + R_outer, s["start"], s["extent"], stroke=0, fill=1)

# Dividers (thin CREAM_BG lines at slice boundaries)
c.setStrokeColorRGB(*CREAM_BG)
c.setLineWidth(1.2)
for s in slices:
    rad = math.radians(s["start"])
    c.line(cx + (R_inner - 0.5) * math.cos(rad), cy + (R_inner - 0.5) * math.sin(rad),
           cx + (R_outer + 0.5) * math.cos(rad), cy + (R_outer + 0.5) * math.sin(rad))

# Inner circular hole
c.setFillColorRGB(*CREAM_BG)
c.circle(cx, cy, R_inner, stroke=0, fill=1)

# Center total
c.setFillColorRGB(0, 0, 0)
# We can use Helvetica or register NeurialGrotesk
c.setFont("Helvetica-Bold", 8.5)
c.drawCentredString(cx, cy + 2.5, "₹")
c.drawCentredString(cx, cy - 8.0, f"{total_bill_amt:,.2f}")

# Leader lines
c.setStrokeColorRGB(0.2, 0.2, 0.2)
c.setLineWidth(0.5)
# Energy leader line (horizontal to left)
ty_energy = page_height - 435.07
c.line(cx - R_outer, ty_energy, 370.0, ty_energy)

# Fixed charges leader line (horizontal to right)
ty_fixed = page_height - 449.27
c.line(cx + R_outer, ty_fixed, 510.0, ty_fixed)

# FPPCA charges leader line (to bottom right)
ty_fppca = page_height - 498.32
# Start from donut boundary near angle 300 deg
rad_fppca = math.radians(300.0)
sx_fppca = cx + R_outer * math.cos(rad_fppca)
sy_fppca = cy + R_outer * math.sin(rad_fppca)
c.line(sx_fppca, ty_fppca, 510.0, ty_fppca)

# Labels
# Energy charges (right-aligned at x=365)
c.setFont("Helvetica-Bold", 8.0)
c.drawRightString(365.0, page_height - 437.0, f"₹{energy_amt:,.2f}")
c.setFont("Helvetica", 7.0)
c.drawRightString(365.0, page_height - 445.5, "Energy Charges")

# Fixed charges (left-aligned at x=515)
c.setFont("Helvetica-Bold", 8.0)
c.drawString(515.0, page_height - 438.0, f"₹{fixed_amt:,.2f}")
c.setFont("Helvetica", 7.0)
c.drawString(515.0, page_height - 446.5, "Fixed Charges")

# FPPCA charges (left-aligned at x=515)
c.setFont("Helvetica-Bold", 8.0)
c.drawString(515.0, page_height - 500.0, f"₹{fppas_amt:,.2f}")
c.setFont("Helvetica", 7.0)
c.drawString(515.0, page_height - 508.5, "FPPCA Charges")

c.save()
buf.seek(0)

# Merge overlay with p0
overlay_reader = PdfReader(buf)
p0.merge_page(overlay_reader.pages[0])

writer = PdfWriter()
writer.add_page(p0)
out_buf = io.BytesIO()
writer.write(out_buf)
out_buf.seek(0)

doc = pdfium.PdfDocument(out_buf)
page = doc[0]
bmp = page.render(scale=2.0)
img = bmp.to_pil()
crop = img.crop((600, 720, 1190, 1080))
crop.save('f:/BILLING/project/scratch/demo_test_donut_render.png')
print("Rendered demo_test_donut_render.png successfully!")
