import math

# Center of donut: cx = 440.0, cy = 394.0 (in PDF coords)
cx = 440.0
cy = 394.0

# Op 741: m [471.84, 423.14] (Energy Charges start)
# Op 744: end at [448.24, 347.08]
# Op 765: m [449.4, 347.31] (FPPCA Charges start)
# Op 766: end at [472.63, 360.31]
# Op 787: m [473.43, 361.18] (Fixed Charges start)
# Op 788: end at [472.66, 422.3]

pts = {
    "Energy start": (471.84, 423.14),
    "Energy end": (448.24, 347.08),
    "FPPCA start": (449.4, 347.31),
    "FPPCA end": (472.63, 360.31),
    "Fixed start": (473.43, 361.18),
    "Fixed end": (472.66, 422.3),
}

for name, (px, py) in pts.items():
    angle_rad = math.atan2(py - cy, px - cx)
    angle_deg = math.degrees(angle_rad) % 360.0
    r = math.sqrt((px - cx)**2 + (py - cy)**2)
    print(f"{name}: angle={angle_deg:.1f}°, r={r:.1f}")
