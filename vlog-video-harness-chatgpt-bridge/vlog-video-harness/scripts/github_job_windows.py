import os
import json
import subprocess
import shutil
import re
import sys
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


def download_video(url):
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    # Screenshots need video only: do not request the audio that failed with 403.
    output = VIDEO_DIR / "source.%(ext)s"
    run(ytdlp_command() + [
        "-f", "bestvideo[height<=1080]/best[height<=1080]",
        "-o", str(output), url
    ])


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



def find_video():

    for f in VIDEO_DIR.iterdir():

        if f.suffix.lower() in [
            ".mp4",
            ".mkv",
            ".webm"
        ]:
            return f


    return None



def get_duration(video):

    result = subprocess.check_output(
        [
            "ffprobe",

            "-v",
            "error",

            "-show_entries",
            "format=duration",

            "-of",
            "default=noprint_wrappers=1:nokey=1",

            str(video)
        ],

        text=True
    )


    return float(result.strip())



def extract_screenshots(video):

    IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    duration = get_duration(video)


    print(
        "VIDEO LENGTH:",
        duration,
        "seconds",
        flush=True
    )


    # 平均取15个时间点

    points = []


    for i in range(15):

        t = duration / 16 * (i + 1)

        points.append(t)



    for index, timestamp in enumerate(points):

        output = IMAGE_DIR / f"{index+1:02d}.jpg"


        run([

            "ffmpeg",

            "-y",
            "-ss",
            str(timestamp),

            "-i",
            str(video),

            "-frames:v",
            "1",

            "-q:v",
            "2",

            str(output)

        ])

        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"Screenshot missing: {output}")
        # One 3:4 image per frame, with a blank white area underneath.
        with Image.open(output) as frame:
            frame = ImageOps.exif_transpose(frame).convert("RGB")
            canvas = Image.new("RGB", (1440, 1920), "white")
            frame.thumbnail((1440, 1440), Image.Resampling.LANCZOS)
            canvas.paste(frame, ((1440 - frame.width) // 2, 0))
            canvas.save(output, quality=95)
        print(f"SCREENSHOT {index + 1}/15 SAVED", flush=True)



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
        print("STEP 1 DOWNLOAD VIDEO", flush=True)
        download_video(url)
        print("STEP 2 DOWNLOAD SUBTITLE", flush=True)
        download_subtitle(url)
        video = find_video()
        if not video:
            raise RuntimeError("video not found")
        print("STEP 3 SCREENSHOTS", flush=True)
        extract_screenshots(video)
    finally:
        print("STEP 4 DELETE VIDEO", flush=True)
        delete_video()

    show_output()


    print(
        "\nDONE",
        flush=True
    )



if __name__ == "__main__":

    main()
