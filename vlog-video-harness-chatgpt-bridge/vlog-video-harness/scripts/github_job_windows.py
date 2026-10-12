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
        "subtitleslangs": ["en-orig"],
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


def select_original_subtitles(info):
    native = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    originals = [key for key in automatic if key.endswith("-orig")]
    declared = info.get("language") or ""
    originals.sort(key=lambda key: (key != declared + "-orig", key != "en-orig", key))
    source = declared or (originals[0][:-5] if originals else "")
    # Exactly one source-language track. Never request auto-translated tracks.
    native_keys = [
        key for key in native if key != "live_chat" and source and (
            key == source or key.split("-")[0] == source.split("-")[0]
        )
    ]
    native_keys.sort(key=lambda key: (key != source, key))
    if native_keys:
        key = native_keys[0]
        tracks = native[key]
    elif originals:
        key = originals[0]
        tracks = automatic[key]
    elif source and source in automatic:
        key = source
        tracks = automatic[key]
    elif not source and len(native) == 1 and "live_chat" not in native:
        key, tracks = next(iter(native.items()))
    else:
        return {}
    vtt = next((track for track in reversed(tracks)
                if track.get("ext") == "vtt" and track.get("url")), None)
    return {key: dict(vtt)} if vtt else {}


def valid_subtitle_files():
    return [
        path for path in SUBTITLE_DIR.glob("*.vtt")
        if path.is_file() and path.stat().st_size > 0
        and path.read_text(encoding="utf-8-sig", errors="replace").lstrip().startswith("WEBVTT")
        and "-->" in path.read_text(encoding="utf-8-sig", errors="replace")
    ]


def retry_delay(error):
    # Honour Retry-After where the underlying HTTP exception exposes it.
    current = error
    seen = set()
    for _ in range(8):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        headers = getattr(current, "headers", None)
        value = headers.get("Retry-After") if headers else None
        if value:
            try:
                return max(60, int(value))
            except (ValueError, TypeError):
                from email.utils import parsedate_to_datetime
                try:
                    return max(60, int(parsedate_to_datetime(value).timestamp() - time.time()))
                except (ValueError, TypeError, OverflowError):
                    pass
        nested = getattr(current, "exc_info", None)
        current = (nested[1] if isinstance(nested, tuple) and len(nested) > 1
                   else getattr(current, "cause", None) or getattr(current, "__cause__", None))
    return 60


def download_subtitle(remote, languages=None):
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    subtitles = select_original_subtitles(remote["info"])
    if languages is not None:
        subtitles = {key: value for key, value in subtitles.items() if key in languages}
    if not subtitles:
        print("No supported original-language VTT subtitles available", flush=True)
        return {}
    pending = {}
    # Reuse existing metadata; skip_download prevents a full video download.
    with yt_dlp.YoutubeDL(remote["options"]) as ydl:
        for language, subtitle in subtitles.items():
            info = dict(remote["info"])
            info["requested_subtitles"] = {language: dict(subtitle)}
            try:
                ydl.process_info(info)
                target = SUBTITLE_DIR / f"subtitle.{language}.vtt"
                if target not in valid_subtitle_files():
                    raise RuntimeError("Subtitle file missing, empty or invalid")
                print(f"SUBTITLE {language} VERIFIED", flush=True)
            except Exception as error:
                limited = "429" in str(error)
                delay = retry_delay(error) if limited else 30
                pending[language] = time.monotonic() + delay
                reason = "HTTP 429 rate limit" if limited else type(error).__name__
                print(f"SUBTITLE {language} FAILED: {reason}; retry after {delay}s",
                      flush=True)
    return pending


def retry_subtitles(remote, pending):
    if not pending:
        return
    for language, ready_at in pending.items():
        remaining = ready_at - time.monotonic()
        if remaining > 300:
            print(f"Subtitle server requested a long cooldown for {language}; "
                  "stop instead of retrying before Retry-After", flush=True)
            continue
        while remaining > 0:
            print(f"SUBTITLE {language}: waiting {math.ceil(remaining)}s before retry",
                  flush=True)
            time.sleep(min(remaining, 15))
            remaining = ready_at - time.monotonic()
        download_subtitle(remote, [language])


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
        # Fill a 4:3 landscape image with a centre crop; no padding or stretching.
        frame = ImageOps.fit(frame, (1440, 1080), Image.Resampling.LANCZOS,
                             centering=(0.5, 0.5))
        frame.save(output, quality=95)


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
        pending_subtitles = download_subtitle(remote)
        print("STEP 3 CAPTURE 15 REMOTE FRAMES", flush=True)
        try:
            extract_screenshots(url, remote)
        finally:
            retry_subtitles(remote, pending_subtitles)
        if not valid_subtitle_files():
            raise RuntimeError(
                "Screenshots saved, but no valid original subtitle file was downloaded. "
                "The job is incomplete; check subtitle availability or rate-limit errors."
            )
    finally:
        delete_video()

    show_output()


    print(
        "\nDONE",
        flush=True
    )



if __name__ == "__main__":

    main()

