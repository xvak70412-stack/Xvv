import os
import json
import subprocess
import shutil
import re
import sys
import time
import math
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageOps
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIR = ROOT / "output"

VIDEO_DIR = OUTPUT_DIR / "video"
IMAGE_DIR = OUTPUT_DIR / "screenshots"
SUBTITLE_DIR = OUTPUT_DIR / "subtitles"


def run(cmd):

    print("\n>>>", " ".join(cmd), flush=True)

    subprocess.run(
        cmd,
        check=True
    )


def clean_dir(path):

    if path.exists():
        shutil.rmtree(path)

    path.mkdir(
        parents=True,
        exist_ok=True
    )


def get_video_url():

    event_path = os.environ.get(
        "GITHUB_EVENT_PATH"
    )

    if not event_path:
        raise Exception(
            "missing github event path"
        )


    with open(
        event_path,
        "r",
        encoding="utf-8"
    ) as f:

        event = json.load(f)


    body = event["issue"]["body"]


    urls = re.findall(
        r"https?://[^\s]+",
        body
    )


    if not urls:
        raise Exception(
            "No YouTube URL found"
        )


    url = urls[0].rstrip(")")


    print(
        "VIDEO URL:",
        url,
        flush=True
    )


    return url



def ytdlp_command():
    cmd = [sys.executable, "-m", "yt_dlp", "--newline",
           "--progress-delta", "5", "--socket-timeout", "30",
           "--retries", "3", "--fragment-retries", "3"]
    cookies = Path(os.environ.get("YOUTUBE_COOKIES_PATH",
                                 r"C:\actions-runner\secrets\cookies.txt"))
    if cookies.is_file():
        cmd += ["--cookies", str(cookies)]
        print("Using configured cookies file", flush=True)
    else:
        print("Cookies file not found; trying public access", flush=True)
    return cmd


def get_remote_video(url):
    options = {
        "format": "bestvideo[height<=1080]/best[height<=1080]",
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 3,
    }
    cookies = Path(os.environ.get("YOUTUBE_COOKIES_PATH",
                                 r"C:\actions-runner\secrets\cookies.txt"))
    if cookies.is_file():
        options["cookiefile"] = str(cookies)
    with yt_dlp.YoutubeDL(options) as ydl:
        # Resolve the selected original video stream without downloading it.
        info = ydl.extract_info(url, download=False)
        if not info or info.get("is_live"):
            raise RuntimeError("A completed video with a known duration is required")
        duration = float(info.get("duration") or 0)
        if not math.isfinite(duration) or duration <= 0:
            raise RuntimeError("Video duration unavailable")
        stream_url = info.get("url", "")
        protocol = info.get("protocol", "")
        if not stream_url.startswith(("https://", "http://")):
            raise RuntimeError("Selected video does not support direct HTTP extraction")
        if protocol not in ("http", "https", "m3u8", "m3u8_native"):
            raise RuntimeError(f"Unsupported remote video protocol: {protocol}")
        headers = dict(info.get("http_headers") or {})
        cookie_header = ydl.cookiejar.get_cookie_header(stream_url)
        if cookie_header:
            headers["Cookie"] = cookie_header
        print(f"REMOTE VIDEO: {info.get('width')}x{info.get('height')}; "
              f"duration {duration}s; format {info.get('format_id')}", flush=True)
        return {"url": stream_url, "duration": duration, "headers": headers}


def download_subtitle(url):

    SUBTITLE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    output = SUBTITLE_DIR / "subtitle"


    try:

        run(ytdlp_command() + [

            "--write-auto-subs",

            "--write-subs",

            "--sub-lang",
            "zh-Hans,zh,en",

            "--sub-format",
            "vtt",

            "--skip-download",

            "-o",
            str(output),

            url
        ])


    except Exception:

        print(
            "Subtitle download failed, continue",
            flush=True
        )



def render_screenshot(output):
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"Screenshot missing: {output.name}")
    with Image.open(output) as frame:
        frame = ImageOps.exif_transpose(frame).convert("RGB")
        canvas = Image.new("RGB", (1440, 1920), "white")
        frame.thumbnail((1440, 1440), Image.Resampling.LANCZOS)
        canvas.paste(frame, ((1440 - frame.width) // 2, 0))
        canvas.save(output, quality=95)


def extract_one_screenshot(remote, index, timestamp):
    output = IMAGE_DIR / f"{index + 1:02d}.jpg"
    # Temporary files ensure failed captures cannot be mistaken for finished images.
    raw = IMAGE_DIR / f"{index + 1:02d}.raw.jpg"
    headers = "".join(
        f"{key}: {value}\r\n"
        for key, value in remote["headers"].items()
        if "\r" not in str(key) + str(value) and "\n" not in str(key) + str(value)
    )
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-rw_timeout", "30000000"]
    if headers:
        cmd += ["-headers", headers]
    cmd += [
        "-ss", str(timestamp), "-threads", "2", "-i", remote["url"],
        "-frames:v", "1", "-q:v", "2", "-threads", "1", str(raw)
    ]
    try:
        # Do not print signed stream URLs, request headers or cookies to logs.
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, timeout=120)
        if result.returncode:
            raise RuntimeError(f"Remote capture failed (ffmpeg exit {result.returncode})")
        render_screenshot(raw)
        raw.replace(output)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Remote capture timed out after 120 seconds") from None
    finally:
        raw.unlink(missing_ok=True)
    print(f"SCREENSHOT {index + 1}/15 SAVED at {timestamp:.1f}s", flush=True)


def extract_screenshots(url, remote):
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    points = [remote["duration"] / 16 * (index + 1) for index in range(15)]
    pending = list(range(15))
    # Limit simultaneous remote requests; refresh signed URLs once on failure.
    workers = min(2, max(1, (os.cpu_count() or 2) // 2))
    for attempt in range(2):
        failures = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                (index, pool.submit(extract_one_screenshot, remote, index, points[index]))
                for index in pending
            ]
            for index, future in futures:
                try:
                    future.result()
                except Exception as error:
                    print(f"SCREENSHOT {index + 1}/15 FAILED: {type(error).__name__}",
                          flush=True)
                    failures.append(index)
        if not failures:
            print(f"SCREENSHOTS FINISHED IN {time.perf_counter() - started:.1f}s",
                  flush=True)
            return
        if attempt == 0:
            print(f"Refreshing stream access; retrying {len(failures)} missing frames",
                  flush=True)
            remote = get_remote_video(url)
            pending = failures
    raise RuntimeError(
        f"Remote extraction failed for images {[index + 1 for index in failures]}; "
        "no full video was downloaded. Successful images are retained."
    )


def delete_video():

    if VIDEO_DIR.exists():

        for f in VIDEO_DIR.iterdir():

            if f.is_file():

                f.unlink()


    print(
        "VIDEO DELETED",
        flush=True
    )



def show_output():

    print(
        "\nOUTPUT FILES:",
        flush=True
    )


    for f in OUTPUT_DIR.rglob("*"):

        print(
            f,
            flush=True
        )



def main():

    url = get_video_url()


    clean_dir(
        OUTPUT_DIR
    )


    try:
        print("STEP 1 READ VIDEO INFO (NO FULL DOWNLOAD)", flush=True)
        remote = get_remote_video(url)
        print("STEP 2 DOWNLOAD SUBTITLE", flush=True)
        download_subtitle(url)
        print("STEP 3 CAPTURE 15 REMOTE FRAMES", flush=True)
        extract_screenshots(url, remote)
    finally:
        delete_video()

    show_output()


    print(
        "\nDONE",
        flush=True
    )



if __name__ == "__main__":

    main()
