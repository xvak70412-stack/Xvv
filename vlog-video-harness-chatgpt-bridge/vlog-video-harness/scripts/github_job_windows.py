import os
import json
import subprocess
import shutil
import re
import sys
import time
import math
from urllib.request import getproxies
from urllib.parse import urlsplit
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



def get_network_proxy():
    override = os.environ.get("YOUTUBE_PROXY")
    proxies = getproxies()
    proxy = override if override is not None else (
        proxies.get("https") or proxies.get("http") or proxies.get("all") or ""
    )
    if proxy and "://" not in proxy:
        proxy = "http://" + proxy
    if proxy and urlsplit(proxy).scheme != "http":
        raise RuntimeError(
            "Remote capture requires an HTTP proxy endpoint. Set YOUTUBE_PROXY "
            "to the HTTP endpoint of your existing proxy, or an empty value for direct access."
        )
    print("NETWORK: shared HTTP proxy" if proxy else "NETWORK: direct connection",
          flush=True)
    return proxy


def get_remote_video(url):
    options = {
        "format": "bestvideo[height<=1080]/best[height<=1080]",
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 3,
        "proxy": get_network_proxy(),
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["zh-Hans", "zh", "en"],
        "subtitlesformat": "vtt",
        "skip_download": True,
        "outtmpl": str(SUBTITLE_DIR / "subtitle.%(ext)s"),
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
        return {"url": stream_url, "duration": duration, "headers": headers,
                "proxy": options["proxy"], "info": info, "options": options}


def download_subtitle(remote):
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    subtitles = remote["info"].get("requested_subtitles") or {}
    if not subtitles:
        print("No requested subtitles available", flush=True)
        return
    # Reuse the existing metadata; do not request the YouTube page a second time.
    with yt_dlp.YoutubeDL(remote["options"]) as ydl:
        for language, subtitle in subtitles.items():
            info = dict(remote["info"])
            info["requested_subtitles"] = {language: dict(subtitle)}
            try:
                ydl.process_info(info)
                print(f"SUBTITLE {language} SAVED", flush=True)
            except Exception as error:
                print(f"SUBTITLE {language} FAILED: {type(error).__name__}; "
                      "other subtitles and screenshots will be retained", flush=True)


def ffmpeg_error(stderr, remote):
    message = stderr.decode("utf-8", errors="replace")
    # Keep diagnostics while stripping access tokens, cookies and proxy credentials.
    for secret in [remote["url"], remote.get("proxy", "")] + list(remote["headers"].values()):
        if secret:
            message = message.replace(str(secret), "[redacted]")
    message = re.sub(r"https?://[^\s'\"]+", "[url]", message)
    message = re.sub(r"(?im)^.*(?:cookie|authorization):.*$", "[private header]", message)
    return message[-1800:].strip() or "No FFmpeg diagnostic output"


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
    proxy = remote.get("proxy", "")
    if proxy:
        cmd += ["-http_proxy", proxy]
    if headers:
        cmd += ["-headers", headers]
    child_env = os.environ.copy()
    # FFmpeg also needs this for nested HLS segment and TLS requests.
    for key in list(child_env):
        if key.lower() in ("http_proxy", "https_proxy", "all_proxy"):
            child_env.pop(key)
    if proxy:
        child_env["http_proxy"] = proxy
        child_env["https_proxy"] = proxy
    cmd += [
        "-ss", str(timestamp), "-threads", "2", "-i", remote["url"],
        "-frames:v", "1", "-q:v", "2", "-threads", "1", str(raw)
    ]
    try:
        # Do not print signed stream URLs, request headers or cookies to logs.
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, timeout=120, env=child_env)
        if result.returncode:
            raise RuntimeError(f"Remote capture failed (ffmpeg exit {result.returncode}): "
                               f"{ffmpeg_error(result.stderr, remote)}")
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
    print("Testing remote capture on image 1/15 before scheduling the rest", flush=True)
    try:
        extract_one_screenshot(remote, 0, points[0])
    except Exception as error:
        raise RuntimeError(
            f"Remote capture preflight failed: {error}. "
            "Stopped before requesting the other 14 images; no full download attempted."
        ) from None
    pending = list(range(1, 15))
    # Retry missing images using existing metadata to avoid repeated site extraction.
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
                    print(f"SCREENSHOT {index + 1}/15 FAILED: {error}",
                          flush=True)
                    failures.append(index)
        if not failures:
            print(f"SCREENSHOTS FINISHED IN {time.perf_counter() - started:.1f}s",
                  flush=True)
            return
        if attempt == 0:
            print(f"Retrying {len(failures)} missing frames with existing stream access",
                  flush=True)
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
        download_subtitle(remote)
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

