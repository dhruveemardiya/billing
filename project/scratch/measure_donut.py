import pdfplumber
import numpy as np
from PIL import Image

# Let's inspect words around donut in demo.pdf
with pdfplumber.open('f:/BILLING/project/demo.pdf') as pdf:
    p0 = pdf.pages[0]
    words = p0.extract_words()
    for w in words:
        if '227.44' in w['text'] or 'MAJOR' in w['text'] or 'Energy' in w['text'] or '149.75' in w['text'] or '55.00' in w['text']:
            print(f"{w['text']}: x0={w['x0']:.2f}, x1={w['x1']:.2f}, top={w['top']:.2f}, bottom={w['bottom']:.2f}")

# Center text '227.44' is at x0=427.32, x1=452.57, top=448.60, bottom=456.60
# Midpoint of 227.44: x = (427.32 + 452.57) / 2 = 439.95 ~ 440.0!
# Rupee symbol '$' is at x0=437.75, x1=442.13, top=440.72, bottom=448.72
# Midpoint y of center: (440.72 + 456.60) / 2 = 448.66
# In pdf coordinates (bottom-left origin): cy = 842 - 448.66 = 393.34
# Notice in existing pdf_generator.py:
# cx = 447.6, cy = page_height - 452.6 ! That was offset from 440.0!

# Now let's measure the radii in the rendered image:
img = Image.open('f:/BILLING/project/scratch/demo_pdf_donut.png')
# The crop was x: 600..1190 (which is 300..595 at scale 2.0), y: 720..1080 (360..540 at scale 2.0)
# Let's find circle bounds
arr = np.array(img.convert('L'))
# Background color is light (~245)
# Dark pixels (<150) belong to donut or text
print("Donut image shape:", arr.shape)
