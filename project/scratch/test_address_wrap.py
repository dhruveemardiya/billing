import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportlab.pdfgen import canvas
import io
import font_manager

registered = font_manager.ensure_template_fonts_registered("demo.pdf")
c = canvas.Canvas(io.BytesIO())

addr = "Building no.7, 404, Anandnagar flats, behind shell petrol pump, Prahlad Nagar, Ahmedabad, Gujarat"

for font_name in ["NeurialGrotesk-Regular"]:
    resolved = font_manager._resolve_font_name(font_name, registered) if hasattr(font_manager, '_resolve_font_name') else font_name
    # try registering or use registered
    for size in [8.0, 7.5, 7.0, 6.5, 6.0]:
        print(f"--- Font: {resolved}, size: {size} ---")
        words = addr.split()
        lines = []
        cur = []
        for w in words:
            test_line = " ".join(cur + [w])
            try:
                w_pt = c.stringWidth(test_line, resolved, size)
            except Exception:
                w_pt = c.stringWidth(test_line, "Helvetica", size)
            if w_pt <= 153.0:
                cur.append(w)
            else:
                if cur:
                    lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))
        print(f"Lines count: {len(lines)}")
        for l in lines:
            print("  ", l)
