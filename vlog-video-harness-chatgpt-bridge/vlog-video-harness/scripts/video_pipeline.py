#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path

YT_RE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{6,})")

def video_id(url: str) -> str:
    m = YT_RE.search(url)
    if not m:
        raise SystemExit("Not a supported YouTube URL")
    return m.group(1)

def ytdlp_cmd(*args):
    return [sys.executable, "-c", "from yt_dlp import main; main()", *args]

def metadata(url: str):
    return json.loads(subprocess.check_output(
        ytdlp_cmd("--no-playlist", "--dump-single-json", "--skip-download", url),
        text=True
    ))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--metadata", action="store_true")
    p.add_argument("--out", default="output/source.json")
    a = p.parse_args()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    data = metadata(a.url)
    result = {
        "id": data.get("id"),
        "title": data.get("title"),
        "duration": data.get("duration"),
        "webpage_url": data.get("webpage_url"),
        "uploader": data.get("uploader"),
        "availability": data.get("availability"),
    }
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
