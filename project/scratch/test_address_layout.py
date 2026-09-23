import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportlab.pdfgen import canvas
import io
import font_manager

registered = font_manager.ensure_template_fonts_registered("demo.pdf")
c = canvas.Canvas(io.BytesIO())
font_name = "NeurialGrotesk-Regular"

addresses = [
    "Building no.7, 404, Anandnagar flats, behind shell petrol pump, Prahlad Nagar, Ahmedabad, Gujarat",
    "House No 399, Vadi Sheri, Vanakbara, Diu",
    "Flat 402, Block C, Shivalik Apartment, Near Shell Petrol Pump, Opposite Reliance Cross Road, Prahlad Nagar, Ahmedabad, Gujarat - 380015",
    "Short Address, Diu"
]

def wrap_and_layout(addr, max_w=153.2, max_h=30.0, top_y=171.5, bottom_y=202.0):
    text = " ".join(addr.split()).upper()
    words = text.split()
    
    # Try font sizes from 8.0 down to 5.5
    best_lines = []
    best_size = 8.0
    for font_size in [8.0, 7.5, 7.0, 6.5, 6.0, 5.5]:
        lines = []
        cur = []
        for w in words:
            candidate = " ".join(cur + [w])
            if c.stringWidth(candidate, font_name, font_size) <= max_w:
                cur.append(w)
            else:
                if cur:
                    lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))
        
        line_spacing = font_size * 1.25
        needed_h = (len(lines) - 1) * line_spacing + font_size
        if needed_h <= max_h or font_size == 5.5:
            best_lines = lines
            best_size = font_size
            break
            
    n = len(best_lines)
    print(f"\nAddress: {addr[:40]}... -> {n} lines at size {best_size}pt:")
    
    if n == 1:
        baselines = [180.0]
    elif n == 2:
        baselines = [179.0, 189.0]
    else:
        # distribute evenly between start_y (~177.0) and end_y (~199.0)
        start_y = top_y + best_size + 0.5
        end_y = bottom_y - 2.0
        step = (end_y - start_y) / (n - 1)
        baselines = [round(start_y + i * step, 1) for i in range(n)]
        
    for i, (l, b) in enumerate(zip(best_lines, baselines)):
        w_pt = c.stringWidth(l, font_name, best_size)
        print(f"  Line {i+1} [y_from_top={b}]: '{l}' (width={w_pt:.1f}pt <= {max_w}pt)")

for a in addresses:
    wrap_and_layout(a)
