import argparse
import json
import re
from pathlib import Path

TIMECODE = re.compile(
    r"(\d{2}:\d{2}:\d{2}[.,]\d+)\s*-->\s*(\d{2}:\d{2}:\d+[.,]\d+)"
)
HAN = re.compile(r"[\u4e00-\u9fff]")
HANGUL = re.compile(r"[\uac00-\ud7af]")
LATIN = re.compile(r"[A-Za-z]")
# Common traditional-only forms; reject these rather than silently output Traditional Chinese.
TRADITIONAL_ONLY = set("體學說會這個們為與時對從來後發現實開關點無過還進應當讓經過問題總結認為覺得聽話愛國書讀寫長見頭場種業辦東車電風雲萬裏樣買賣請謝歡難處號選擇親親")
CN_KEYWORDS = ("因为", "但是", "所以", "其实", "如果", "不要", "一定", "重要", "生活", "工作", "改变", "永远", "从来", "自己", "人生", "成长", "选择", "相信", "努力", "成功", "失败", "坚持", "价值", "关系", "人性", "真正", "意味着", "记住", "只有", "才能", "学会", "自由", "勇敢", "恐惧", "幸福", "痛苦", "世界", "别人", "内心")

def sec(x):
    h, mi, se = x.replace(",", ".").split(":")
    return int(h) * 3600 + int(mi) * 60 + float(se)

def clean_text(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\{\\an\d+\}", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def is_simplified_chinese(text):
    han = len(HAN.findall(text))
    if han < 4 or HANGUL.search(text):
        return False
    latin = len(LATIN.findall(text))
    if latin > max(2, han * 0.08):
        return False
    if any(ch in TRADITIONAL_ONLY for ch in text):
        return False
    return True

def cues(path):
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    blocks = re.split(r"\n\s*\n", raw)
    for block in blocks:
        m = TIMECODE.search(block)
        if not m:
            continue
        lines = block.splitlines()
        idx = next((i for i, line in enumerate(lines) if TIMECODE.search(line)), None)
        if idx is None:
            continue
        text = clean_text(" ".join(lines[idx + 1:]))
        if not text or text.startswith(("♪", "[Music", "(Music", "[Applause")):
            continue
        if not is_simplified_chinese(text):
            continue
        out.append({"start": sec(m.group(1)), "end": sec(m.group(2)), "text": text})
    return out

def score(text):
    n = len(text)
    s = min(n, 100) / 18.0
    if 12 <= n <= 55:
        s += 2.5
    if any(p in text for p in ("。", "！", "？", "；")):
        s += 1.5
    if any(k in text for k in CN_KEYWORDS):
        s += 2.5
    if any(k in text for k in ("不是", "而是", "真正", "本质", "原因", "结果", "意味着", "关键", "记住", "值得", "必须", "从不", "永远")):
        s += 1.5
    # Penalize likely fragments and very short conversational fillers.
    if len(text) < 10:
        s -= 3
    if any(f in text for f in ("嗯嗯", "哈哈", "谢谢大家", "欢迎回来", "订阅点赞")):
        s -= 5
    return s

def make_candidates(all_cues, images):
    windows = []
    for i in range(len(all_cues)):
        group = []
        start = all_cues[i]["start"]
        for c in all_cues[i:i + 4]:
            if c["start"] - start > 10:
                break
            # Keep adjacent Chinese cues only; stop at a long pause.
            if group and c["start"] - group[-1]["end"] > 2.5:
                break
            group.append(c)
            if sum(len(x["text"]) for x in group) >= 32:
                break
        text = "".join(c["text"] for c in group).strip()
        if len(text) < 10 or not is_simplified_chinese(text):
            continue
        windows.append({
            "start": group[0]["start"],
            "end": group[-1]["end"],
            "text": text,
            "cues": group,
            "score": score(text),
        })
    windows.sort(key=lambda x: x["score"], reverse=True)
    chosen = []
    for w in windows:
        if any(abs(w["start"] - c["start"]) < 18 for c in chosen):
            continue
        chosen.append(w)
        if len(chosen) >= images:
            break
    chosen.sort(key=lambda x: x["start"])
    return chosen

def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("subs")
    p.add_argument("--images", type=int, default=5)
    p.add_argument("--mode", default="auto")
    p.add_argument("--out", required=True)
    a = p.parse_args()

    # Never merge different subtitle languages. Pick the file that actually contains
    # the most simplified-Chinese cues, preferring Chinese language filenames.
    files = sorted(Path(a.subs).glob("*.vtt"))
    file_cues = []
    for f in files:
        parsed = cues(f)
        if parsed:
            name = f.name.lower()
            lang_bonus = 1000 if any(tag in name for tag in ("zh-hans", "zh_cn", "zh-cn", "zh-hant", "zh-tw", "zh")) else 0
            file_cues.append((lang_bonus + len(parsed), f, parsed))
    file_cues.sort(key=lambda x: x[0], reverse=True)
    selected_file = file_cues[0][1] if file_cues else None
    all_cues = file_cues[0][2] if file_cues else []
    chosen = make_candidates(all_cues, a.images) if all_cues else []

    images = []
    for i, w in enumerate(chosen, 1):
        images.append({
            "title": f"candidate-{i:02d}",
            "times": [round(c["start"], 3) for c in w["cues"]],
            "lines": [c["text"] for c in w["cues"]],
            "quote": w["text"],
            "score": round(w["score"], 3),
        })
    m = {
        "mode": a.mode,
        "subtitle_files": [str(selected_file)] if selected_file else [],
        "subtitle_cue_count": len(all_cues),
        "selection": "simplified_chinese_quote_v2",
        "needs_native_pixel_confirmation": a.mode == "auto",
        "images": images,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(m, ensure_ascii=True, indent=2))

if __name__ == "__main__":
    main()
