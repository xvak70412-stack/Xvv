import argparse
import json
import re
from pathlib import Path

TIMECODE = re.compile(
    r"(\d{2}:\d{2}:\d{2}[.,]\d+)\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d+)"
)

def sec(x):
    h, mi, se = x.replace(",", ".").split(":")
    return int(h) * 3600 + int(mi) * 60 + float(se)

def clean_text(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\{\\an\d+\}", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

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
        try:
            idx = next(i for i, line in enumerate(lines) if TIMECODE.search(line))
        except StopIteration:
            continue
        text = clean_text(" ".join(lines[idx + 1:]))
        if not text or text.startswith(("♪", "[Music", "(Music", "[Applause")):
            continue
        out.append({"start": sec(m.group(1)), "end": sec(m.group(2)), "text": text})
    return out

def score(text):
    n = len(text)
    s = min(n, 120) / 20.0
    if 18 <= n <= 90:
        s += 3
    if any(p in text for p in ("。", "！", "？", ".", "!", "?")):
        s += 1.5
    if any(k in text.lower() for k in (
        "because", "but", "why", "learn", "feel", "think", "important",
        "life", "work", "love", "change", "always", "never", "remember",
    )):
        s += 1.5
    if any(k in text for k in ("因为", "但是", "所以", "其实", "如果", "不要", "一定", "重要", "生活", "工作", "改变", "永远", "从来")):
        s += 2
    if text.count(" ") > 2:
        s += 0.5
    return s

def make_candidates(all_cues, images):
    # Build short adjacent subtitle windows, then rank them.
    windows = []
    for i in range(len(all_cues)):
        group = []
        chars = 0
        start = all_cues[i]["start"]
        for c in all_cues[i:i + 4]:
            if c["start"] - start > 14:
                break
            group.append(c)
            chars += len(c["text"])
            if chars >= 35:
                break
        if not group:
            continue
        text = " ".join(c["text"] for c in group).strip()
        if len(text) < 12:
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

    all_cues = []
    files = sorted(Path(a.subs).glob("*.vtt"))
    for f in files:
        all_cues.extend(cues(f))
    all_cues.sort(key=lambda x: x["start"])

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
        "subtitle_files": [str(x) for x in files],
        "subtitle_cue_count": len(all_cues),
        "selection": "heuristic_quote_v1",
        "needs_native_pixel_confirmation": a.mode == "auto",
        "images": images,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(m, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
