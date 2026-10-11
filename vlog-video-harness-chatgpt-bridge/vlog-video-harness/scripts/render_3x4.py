import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

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
            band = im.crop((0, int(im.height * 0.72), im.width, im.height))
            band = ImageOps.grayscale(band)
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

# Export each candidate as an individual, full-frame image.
# Do not add subtitles, dialogue panels, labels, or contact sheets.
rendered = []
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    for n, item in enumerate(manifest.get("images", []), 1):
        times = item.get("times", [])
        if not times:
            continue

        # If Tesseract happens to be installed, prefer a frame whose lower
        # band has no detected text. Otherwise use the first candidate time.
        chosen = None
        for i, timestamp in enumerate(times):
            frame = td / f"candidate-{n:02d}-{i:02d}.jpg"
            grab(timestamp, frame)
            if not has_bottom_text(frame):
                chosen = frame
                break
            if chosen is None:
                chosen = frame

        if chosen is None:
            continue
        filename = f"{n:02d}-{safe_name(item.get('title', f'candidate-{n:02d}'), f'candidate-{n:02d}')}.jpg"
        target = out / filename
        with Image.open(chosen) as im:
            im.convert("RGB").save(target, quality=95)
        rendered.append(target)

print(f"render complete: {len(rendered)} individual candidate images")
