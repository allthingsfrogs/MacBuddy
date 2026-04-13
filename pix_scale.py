from pathlib import Path
from PIL import Image

ASSETS_DIR = Path("assets")
SCALE = 4  # 400% — 68x56 → 272x224
TARGET_SIZE = (272, 224)

for png in ASSETS_DIR.rglob("*.png"):
    img = Image.open(png)
    if img.size == TARGET_SIZE:
        print(f"Skipped {png} (already {img.width}x{img.height})")
        continue
    scaled = img.resize(TARGET_SIZE, Image.NEAREST)
    scaled.save(png)
    print(f"Scaled {png} ({img.width}x{img.height} → {TARGET_SIZE[0]}x{TARGET_SIZE[1]})")

print("Done.")
