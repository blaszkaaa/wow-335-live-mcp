"""Generate application icons during build; no font files or binary repo blobs."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1] / "src-tauri" / "icons"
root.mkdir(parents=True, exist_ok=True)
image = Image.new("RGBA", (256, 256), (12, 24, 31, 255))
d = ImageDraw.Draw(image)
d.rounded_rectangle((13, 13, 243, 243), radius=55, fill=(18, 68, 60),
                    outline=(43, 190, 150), width=7)
d.rounded_rectangle((35, 35, 221, 221), radius=38, outline=(41, 111, 101), width=3)
# Stylized W logo using strokes, no fonts or branding assets needed.
points = [(56, 79), (94, 180), (128, 113), (164, 180), (204, 79)]
d.line(points, fill=(213, 253, 236), width=20, joint="curve")
for px, py in points:
    d.ellipse((px-10, py-10, px+10, py+10), fill=(213, 253, 236))
image.save(root / "icon.png")
image.save(root / "icon.ico", format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
