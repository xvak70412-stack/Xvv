import argparse
import json
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

o = Path(a.out)
o.mkdir(parents=True, exist_ok=True)
m = json.loads(Path(a.manifest).read_text(encoding="utf-8"))

W = a.width
H = round(W * 4 / 3)

# 保留原来的拼图布局，字幕直接叠加在画面上
VIDEO_H = H
HERO_H = round(VIDEO_H * 0.70)


def grab(t, dest):
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(t), "-i", a.video,
         "-frames:v", "1", "-q:v", "2", str(dest)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def load_font(size):
    font_paths = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for font_path in font_paths:
        if Path(font_path).is_file():
            try:
                return ImageFont.truetype(font_path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def wrap_chinese(draw, text, font, max_width):
    lines = []
    current = ""
    for ch in text:
        trial = current + ch
        if current and draw.textbbox((0, 0), trial, font=font)[2] > max_width:
            lines.append(current)
            current = ch
        else:
            current = trial
    if current:
        lines.append(current)
    return lines



for n, item in enumerate(m.get("images", []), 1):
    times = item.get("times", [])
    if not times:
        continue

    # 只生成无字幕拼图；字幕翻译和金句后续单独处理。
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        paths = []
        for i, t in enumerate(times):
            frame_path = td / f"frame-{i:02d}.jpg"
            grab(t, frame_path)
            paths.append(frame_path)

        canvas = Image.new("RGB", (W, H), "white")

        # 主截图放在拼图顶部，不叠加字幕
        hero = Image.open(paths[0]).convert("RGB")
        hero = ImageOps.fit(hero, (W, HERO_H))
        canvas.paste(hero, (0, 0))

        # 下方最多保留 3 条截图条，不叠加字幕
        strip_top = HERO_H
        strip_height = VIDEO_H - HERO_H
        strip_paths = paths[1:4] if len(paths) > 1 else []
        if strip_paths and strip_height > 0:
            each_h = max(1, strip_height // len(strip_paths))
            for i, frame_path in enumerate(strip_paths):
                y = strip_top + i * each_h
                if y >= VIDEO_H:
                    break
                h = (VIDEO_H - y) if i == len(strip_paths) - 1 else min(each_h, VIDEO_H - y)
                if h <= 0:
                    continue
                with Image.open(frame_path) as frame:
                    strip = ImageOps.fit(frame.convert("RGB"), (W, h))
                    canvas.paste(strip, (0, y))
        canvas.save(
            o / f"{n:02d}-{item.get('title', f'candidate-{n:02d}')}.jpg",
            quality=95,
        )

images = sorted(p for p in o.glob("*.jpg") if p.name != "contact_sheet.jpg")
if images:
    thumbs = []
    for image_path in images:
        with Image.open(image_path) as im:
            im.thumbnail((360, 480))
            thumbs.append((image_path.name, im.copy()))

    sheet = Image.new("RGB", (360 * len(thumbs), 520), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(thumbs):
        sheet.paste(im, (i * 360, 0))
        draw.text((i * 360 + 5, 490), name, fill="black")
    sheet.save(o / "contact_sheet.jpg", quality=92)

print("render complete")
