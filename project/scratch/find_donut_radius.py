import numpy as np
from PIL import Image

img = Image.open('f:/BILLING/project/scratch/demo_pdf_donut.png')
# crop was (600, 720, 1190, 1080) at scale 2.0 (so in PDF coords: x0=300, y0_from_top=360)
# Let's find circle center and inner/outer radii
arr = np.array(img.convert('L'))
# background is around 245
# circle has rays that are darker (<220)
# Find vertical column sum and horizontal row sum
# In crop image coordinates:
# Midpoint of 227.44 in crop image:
# x in PDF: 440.0 -> in crop: (440 - 300) * 2 = 280
# y in PDF: 448.6 -> in crop: (448.6 - 360) * 2 = 177.2
cx_crop = 280.0
cy_crop = 177.2

# Check horizontal cross section through cy_crop
row = arr[int(cy_crop), :]
# Print where dark pixels are along this horizontal line
dark_indices = np.where(row < 220)[0]
print("Dark x indices on row", int(cy_crop), ":", dark_indices)

# Left outer edge, left inner edge, right inner edge, right outer edge:
# Let's find radial distances from (cx_crop, cy_crop):
H, W = arr.shape
y_idx, x_idx = np.ogrid[:H, :W]
dist = np.sqrt((x_idx - cx_crop)**2 + (y_idx - cy_crop)**2)

# For dist in range 0..200, compute average intensity
d_bins = np.arange(0, 180, 2)
intensities = []
for d in d_bins:
    mask = (dist >= d) & (dist < d + 2)
    intensities.append(arr[mask].mean())

for d, val in zip(d_bins, intensities):
    if val < 235: # has dark pixels
        print(f"dist={d/2:.1f} pt in PDF: mean={val:.1f}")
