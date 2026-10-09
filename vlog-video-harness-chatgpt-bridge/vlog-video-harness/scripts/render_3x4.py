import argparse
import json
import subprocess
import tempfile
import re
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


def split_caption_lines(text):
    """把字幕拆成简短句子，避免整段文字重复铺满拼图。"""
    text = re.sub(r"\s+", "", str(text or ""))
    parts = re.split(r"(?<=[。！？；，.!?;])", text)
    result = []
    for part in parts:
        part = part.strip(" ，。！？；：,.!?;:")
        if len(part) >= 4 and part not in result:
            result.append(part)
    short = []
    for part in result:
        while len(part) > 22:
            short.append(part[:20])
            part = part[20:]
        if part:
            short.append(part)
    return short or ([text[:20]] if text else [])


def draw_caption_bar(image, text):
    """在截图底部叠加半透明黑底白字字幕。"""
    if not text:
        return image

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    max_width = round(image.width * 0.92)
    font_size = max(16, round(W * 0.034))
    min_font_size = max(14, round(W * 0.020))

    while font_size >= min_font_size:
        font = load_font(font_size)
        lines = wrap_chinese(draw, text, font, max_width)
        line_height = draw.textbbox((0, 0), "中文Ag", font=font)[3] + 4
        if len(lines) <= 2 and len(lines) * line_height <= image.height * 0.72:
            break
        font_size -= 2

    font = load_font(max(font_size, min_font_size))
    lines = wrap_chinese(draw, text, font, max_width)
    line_height = draw.textbbox((0, 0), "中文Ag", font=font)[3] + 4
    # 若单条截图太矮，只显示最后一行，避免字幕挤满画面
    max_lines = max(1, min(2, int(image.height * 0.72 // max(1, line_height))))
    lines = lines[-max_lines:]
    total_height = len(lines) * line_height
    pad_y = max(3, round(font_size * 0.22))
    y0 = max(0, image.height - total_height - pad_y * 2)

    draw.rectangle((0, y0, image.width, image.height), fill=(0, 0, 0, 175))
    y = y0 + pad_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=1)
        text_width = bbox[2] - bbox[0]
        x = (image.width - text_width) // 2
        draw.text((x, y), line, font=font, fill="white",
                  stroke_width=1, stroke_fill="black")
        y += line_height

    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")

for n, item in enumerate(m.get("images", []), 1):
    times = item.get("times", [])
    if not times:
        continue

    # 主画面显示重点短句，下方截图条显示不同短句。
    caption_lines = split_caption_lines(item.get("quote", ""))
    if not caption_lines:
        continue
    quote = caption_lines[0]

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        paths = []
        for i, t in enumerate(times):
            frame_path = td / f"frame-{i:02d}.jpg"
            grab(t, frame_path)
            paths.append(frame_path)

        canvas = Image.new("RGB", (W, H), "white")

        # 主截图放在拼图顶部，并叠加白字黑底中文字幕
        hero = Image.open(paths[0]).convert("RGB")
        hero = ImageOps.fit(hero, (W, HERO_H))
        hero = draw_caption_bar(hero, quote)
        canvas.paste(hero, (0, 0))

        # 下方继续排列截图条，每条显示不同短句，避免字幕重复
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
                    strip_quote = caption_lines[i + 1] if i + 1 < len(caption_lines) else ""
                    strip = draw_caption_bar(strip, strip_quote)
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
