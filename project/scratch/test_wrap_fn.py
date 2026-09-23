from reportlab.pdfgen import canvas
import io
import font_manager

def wrap_address_lines(c, raw_address: str, font_name: str, max_width: float, max_height: float, font_sizes=(8.0, 7.5, 7.0, 6.5, 6.0, 5.5)):
    clean_addr = " ".join(str(raw_address or "").split()).upper()
    if not clean_addr:
        return [], 8.0

    words = clean_addr.split()
    best_lines = []
    best_size = font_sizes[-1]

    for size in font_sizes:
        lines = []
        cur = []
        for w in words:
            candidate = " ".join(cur + [w])
            try:
                w_pt = c.stringWidth(candidate, font_name, size)
            except Exception:
                w_pt = c.stringWidth(candidate, "Helvetica", size)
            if w_pt <= max_width:
                cur.append(w)
            else:
                if cur:
                    lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))

        line_spacing = size * 1.25
        needed_height = (len(lines) - 1) * line_spacing + size
        if needed_height <= max_height or size == font_sizes[-1]:
            best_lines = lines
            best_size = size
            break

    return best_lines, best_size

c = canvas.Canvas(io.BytesIO())
addr = "Building no.7, 404, Anandnagar flats, behind shell petrol pump, Prahlad Nagar, Ahmedabad, Gujarat"

for layout, font_name, mw, mh in [
    ("classic_neurial", "NeurialGrotesk-Regular", 153.2, 30.0),
    ("modern_manrope", "Manrope-Regular", 170.0, 60.0),
]:
    lines, sz = wrap_address_lines(c, addr, "Helvetica", mw, mh)
    print(f"=== {layout} ===")
    print(f"Size: {sz}pt, Lines: {len(lines)}")
    for l in lines:
        print("  ", l)
