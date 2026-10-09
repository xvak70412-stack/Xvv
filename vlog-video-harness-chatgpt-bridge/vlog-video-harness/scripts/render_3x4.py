import argparse
import json
import re
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

# 画面区域：保留视频画面；字幕单独放在底部白色区域
VIDEO_H = round(H * 0.76)
TEXT_H = H - VIDEO_H


def grab(t, dest):
    subprocess.run(
        [
            "ffmpeg", "-y", "-ss", str(t), "-i", a.video,
            "-frames:v", "1", "-q:v", "2", str(dest)
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def is_chinese_char(ch):
    return "\u4e00" <= ch <= "\u9fff"


def chinese_quote(item):
    """只提取简体中文金句，不把其他语言拼进去。"""
    candidates = []

    # 优先使用原始字幕行，而不是混合语言的 quote
    for line in item.get("lines", []):
        if not isinstance(line, str):
            continue

        line = line.strip()
        if not line:
            continue

        # 去掉不属于中文金句的字符，只保留中文、常用标点和数字
        cleaned = "".join(
            ch for ch in line
            if is_chinese_char(ch)
            or ch in "，。！？；：、（）《》“”‘’—… "
            or ch.isdigit()
        ).strip()

        chinese_count = sum(is_chinese_char(ch) for ch in cleaned)
        if chinese_count >= 4:
            candidates.append((chinese_count, cleaned))

    # 选择中文信息最多的一行，避免把韩文、英文混入字幕
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    # 备用：如果只有 quote 字段，则只保留其中的中文字符和中文标点
    quote = item.get("quote", "")
    if isinstance(quote, str):
        cleaned = "".join(
            ch for ch in quote
            if is_chinese_char(ch)
            or ch in "，。！？；：、（）《》“”‘’—… "
            or ch.isdigit()
        ).strip()
        if sum(is_chinese_char(ch) for ch in cleaned) >= 4:
            return cleaned

    return ""


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
    margin_y = round(TEXT_H * 0.12)
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

    quote = chinese_quote(item)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        hero_path = td / "hero.jpg"
        grab(times[0], hero_path)

        canvas = Image.new("RGB", (W, H), "white")

        # 上方保留主画面，采用等比例裁切填充
        hero = Image.open(hero_path).convert("RGB")
        hero = ImageOps.fit(hero, (W, VIDEO_H))
        canvas.paste(hero, (0, 0))

        # 只在底部白色区域绘制中文金句
        draw_quote(canvas, quote)

        canvas.save(
            o / f"{n:02d}-{item.get('title', f'candidate-{n:02d}')}.jpg",
            quality=95,
        )

# 生成联系表
images = sorted(
    p for p in o.glob("*.jpg")
    if p.name != "contact_sheet.jpg"
)

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
