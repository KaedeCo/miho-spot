"""Generate an app icon for Miho-spot Desktop."""
from PIL import Image, ImageDraw, ImageFont

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background circle with gradient-like effect (deep purple)
cx, cy, r = SIZE // 2, SIZE // 2, SIZE // 2 - 8
for i in range(r, 0, -1):
    t = i / r
    r_val = int(99 + (15 - 99) * t)
    g_val = int(102 + (15 - 102) * t)
    b_val = int(241 + (23 - 241) * t)
    draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(r_val, g_val, b_val, 255))

# Inner accent ring
draw.ellipse([cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4],
             outline=(167, 139, 250, 200), width=3)

# "M" letter in white
try:
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 140)
except:
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 140)
    except:
        font = ImageFont.load_default()
bbox = draw.textbbox((0, 0), "M", font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
draw.text((cx - tw // 2, cy - th // 2 - 6), "M", fill="white", font=font)

# Small sparkle dots
for angle in [45, 135, 225, 315]:
    import math
    rad = math.radians(angle)
    dx, dy = int((r + 5) * math.cos(rad)), int((r + 5) * math.sin(rad))
    draw.ellipse([cx + dx - 5, cy + dy - 5, cx + dx + 5, cy + dy + 5],
                 fill=(99, 102, 241, 220))

img.save("app_icon.png")
img.save("app_icon.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("Icon generated: app_icon.ico")
