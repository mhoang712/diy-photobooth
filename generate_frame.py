import cv2
import numpy as np
import os

# Create a 1920x1080 transparent image
width, height = 1920, 1080
image = np.zeros((height, width, 4), dtype=np.uint8)

# Add a background color with some opacity (e.g. white, 255 alpha for background)
image[:, :] = [255, 255, 255, 255] # BGRA: White background

# Let's create 4 cutouts (transparent holes)
# Layout: 2x2 grid
cutout_width, cutout_height = 600, 400
margin_x = (width - (2 * cutout_width)) // 3
margin_y = (height - (2 * cutout_height)) // 3

# Top Left
image[margin_y:margin_y+cutout_height, margin_x:margin_x+cutout_width] = [0, 0, 0, 0]
# Top Right
image[margin_y:margin_y+cutout_height, margin_x*2+cutout_width:margin_x*2+2*cutout_width] = [0, 0, 0, 0]
# Bottom Left
image[margin_y*2+cutout_height:margin_y*2+2*cutout_height, margin_x:margin_x+cutout_width] = [0, 0, 0, 0]
# Bottom Right
image[margin_y*2+cutout_height:margin_y*2+2*cutout_height, margin_x*2+cutout_width:margin_x*2+2*cutout_width] = [0, 0, 0, 0]

os.makedirs('static/assets', exist_ok=True)
cv2.imwrite('static/assets/frame.png', image)
print("Generated static/assets/frame.png")
