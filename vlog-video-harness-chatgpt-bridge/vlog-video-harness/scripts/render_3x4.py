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

# 上方保留原来的拼图效果，下方独立留白放简体中文金句
VIDEO_H = round(H * 0.70)
TEXT_H = H - VIDEO_H
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


def draw_quote(canvas, text):
    if not text:
        return

    draw = ImageDraw.Draw(canvas)
    margin_x = round(W * 0.07)
    margin_y = round(TEXT_H * 0.10)
    max_width = W - margin_x * 2
    font_size = max(24, round(W * 0.045))
    min_font_size = max(20, round(W * 0.026))

    while font_size >= min_font_size:
        font = load_font(font_size)
        lines = wrap_chinese(draw, text, font, max_width)
        line_height = draw.textbbox((0, 0), "中文Ag", font=font)[3] + 8
        if len(lines) * line_height <= TEXT_H - margin_y * 2:
            break
        font_size -= 2

    font = load_font(max(font_size, min_font_size))
    lines = wrap_chinese(draw, text, font, max_width)
    line_height = draw.textbbox((0, 0), "中文Ag", font=font)[3] + 8
    total_height = len(lines) * line_height
    y = VIDEO_H + max(0, (TEXT_H - total_height) // 2)

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (W - text_width) // 2
        draw.text((x, y), line, font=font, fill=(15, 15, 15))
        y += line_height


for n, item in enumerate(m.get("images", []), 1):
    times = item.get("times", [])
    if not times:
        continue

    # 分析脚本已先筛选简体中文字幕，这里直接使用完整金句，不再截断成单行。
    quote = str(item.get("quote", "")).strip()

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        paths = []
        for i, t in enumerate(times):
            frame_path = td / f"frame-{i:02d}.jpg"
            grab(t, frame_path)
            paths.append(frame_path)

        canvas = Image.new("RGB", (W, H), "white")

        # 主截图占拼图区域上方约 70%
        hero = Image.open(paths[0]).convert("RGB")
        hero = ImageOps.fit(hero, (W, HERO_H))
        canvas.paste(hero, (0, 0))

        # 余下区域按时间顺序排列截图条，保留原拼图风格
        strip_top = HERO_H
        strip_height = VIDEO_H - HERO_H
        if paths and strip_height > 0:
            each_h = max(1, strip_height // len(paths))
            for i, frame_path in enumerate(paths):
                y = strip_top + i * each_h
                if y >= VIDEO_H:
                    break
                h = (VIDEO_H - y) if i == len(paths) - 1 else min(each_h, VIDEO_H - y)
                if h <= 0:
                    continue
                with Image.open(frame_path) as frame:
                    strip = ImageOps.fit(frame.convert("RGB"), (W, h))
                    canvas.paste(strip, (0, y))

        draw_quote(canvas, quote)
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
