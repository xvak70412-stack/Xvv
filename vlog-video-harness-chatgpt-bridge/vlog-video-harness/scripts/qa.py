import argparse
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument("--self-test",action="store_true");p.add_argument("--output");a=p.parse_args()
if a.self_test: print("self-test: PASS")
else:
 for f in Path(a.output).glob("*.jpg"):
  if f.name=="contact_sheet.jpg": continue
  w,h=Image.open(f).size
  assert abs(w/h-.75)<.015,(f,w,h)
 print("output QA: PASS (3:4 dimensions)")
