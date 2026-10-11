import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps, ImageDraw, ImageFont

p = argparse.ArgumentParser()
p.add_argument("video")
p.add_argument("manifest")
p.add_argument("--out")
p.add_argument("--width", type=int, default=1440)
a = p.parse_args()

out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
manifest = json.loads(Path(a.manifest).read_text(encoding="utf-8"))

def grab(t, dest):
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(t), "-i", a.video,
         "-frames:v", "1", "-q:v", "2", str(dest)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
    )

def has_bottom_text(image_path):
    """Best-effort subtitle screening using Tesseract OCR, if installed."""
    exe = shutil.which("tesseract")
    if not exe:
        return False
    try:
        with Image.open(image_path) as im:
            im = im.convert("RGB")
            # Subtitle text usually sits in the lower quarter. Ignore most of
            # the scene and OCR only this band to reduce unrelated detections.
            band = im.crop((0, int(im.height * 0.72), im.width, im.height))
            band = ImageOps.grayscale(band)
            result = subprocess.run(
                [exe, "stdin", "stdout", "--psm", "6"],
                input=b"", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                check=False,
            ) if False else None
            # Tesseract accepts an image filename; use a temporary PNG.
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_path = Path(tmp.name)
            try:
                band.save(temp_path)
                result = subprocess.run(
                    [exe, str(temp_path), "stdout", "--psm", "6"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, check=False,
                )
                words = [w for w in result.stdout.split() if any(ch.isalnum() for ch in w)]
                return len(words) >= 2
            finally:
                temp_path.unlink(missing_ok=True)
    except Exception:
        return False

def safe_name(value, fallback):
    name = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in str(value))
    return name.strip("-.") or fallback

# Render one full frame per candidate. Do not create nested strips from the
# same frame, which caused the previous collage to look duplicated/cropped.
rendered = []
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    for n, item in enumerate(manifest.get("images", []), 1):
        times = item.get("times", [])
        if not times:
            continue

        # Try the available candidate timestamps in order and prefer one
        # without OCR-detected text in the bottom subtitle band.
        chosen = None
        for i, timestamp in enumerate(times):
            frame = td / f"candidate-{n:02d}-{i:02d}.jpg"
            grab(timestamp, frame)
            if not has_bottom_text(frame):
                chosen = frame
                break
            if chosen is None:
                chosen = frame  # fallback if every timestamp contains text

        if chosen is None:
            continue
        filename = f"{n:02d}-{safe_name(item.get('title', f'candidate-{n:02d}'), f'candidate-{n:02d}')}.jpg"
        target = out / filename
        with Image.open(chosen) as im:
            im.convert("RGB").save(target, quality=95)
        rendered.append(target)

# A clean 3-column x 2-row contact sheet. Each image is contained (not cropped)
# within its cell, with a white background and a filename label.
cell_w = max(360, a.width // 3)
cell_h = round(cell_w * 3 / 4)
label_h = 28
sheet = Image.new("RGB", (cell_w * 3, (cell_h + label_h) * 2), "white")
draw = ImageDraw.Draw(sheet)
font = ImageFont.load_default()
for i, path in enumerate(rendered[:5]):
    col, row = i % 3, i // 3
    x, y = col * cell_w, row * (cell_h + label_h)
    with Image.open(path) as im:
        im = ImageOps.contain(im.convert("RGB"), (cell_w, cell_h))
        px = x + (cell_w - im.width) // 2
        py = y + (cell_h - im.height) // 2
        sheet.paste(im, (px, py))
    draw.text((x + 8, y + cell_h + 6), path.name, fill="black", font=font)
sheet.save(out / "contact_sheet.jpg", quality=92)
print("render complete")
