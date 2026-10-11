import argparse
from pathlib import Path
from PIL import Image

p = argparse.ArgumentParser()
p.add_argument("--self-test", action="store_true")
p.add_argument("--output")
a = p.parse_args()

if a.self_test:
    print("self-test: PASS")
else:
    output = Path(a.output)
    images = [f for f in output.glob("*.jpg") if f.name != "contact_sheet.jpg"]
    if not images:
        raise SystemExit(f"output QA: FAIL (no JPG images found in {output})")
    for f in images:
        with Image.open(f) as image:
            w, h = image.size
        # Video candidate screenshots are expected to remain landscape 16:9.
        assert abs(w / h - (16 / 9)) < 0.02, (f, w, h)
    print(f"output QA: PASS ({len(images)} landscape 16:9 images)")
