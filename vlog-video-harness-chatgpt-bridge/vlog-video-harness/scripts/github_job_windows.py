import os
import json
import subprocess
import shutil
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIR = ROOT / "output"

VIDEO_DIR = OUTPUT_DIR / "video"
IMAGE_DIR = OUTPUT_DIR / "screenshots"
SUBTITLE_DIR = OUTPUT_DIR / "subtitles"


def run(cmd):
    print("\n>>>", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


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
            "No YouTube URL found in issue"
        )


    url = urls[0].rstrip(")")

    print(
        "VIDEO URL:",
        url,
        flush=True
    )

    return url



def download_video(url):

    VIDEO_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    output = VIDEO_DIR / "source.%(ext)s"


    run([
        "yt-dlp",

        "-f",
        "bestvideo[height<=1080]+bestaudio/best",

        "--merge-output-format",
        "mp4",

        "-o",
        str(output),

        url
    ])



def download_subtitle(url):

    SUBTITLE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    output = SUBTITLE_DIR / "subtitle"


    run([
        "yt-dlp",

        "--write-auto-subs",

        "--write-subs",

        "--sub-lang",
        "zh,en",

        "--sub-format",
        "vtt",

        "--skip-download",

        "-o",
        str(output),

        url
    ])



def find_video():

    for f in VIDEO_DIR.iterdir():

        if f.suffix.lower() in [
            ".mp4",
            ".mkv",
            ".webm"
        ]:
            return f

    return None



def extract_screenshots(video):

    IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    for i in range(15):

        timestamp = i * 60

        output = IMAGE_DIR / f"{i+1:02d}.jpg"


        run([
            "ffmpeg",

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



def delete_video():

    if VIDEO_DIR.exists():

        for f in VIDEO_DIR.iterdir():

            if f.is_file():

                f.unlink()


    print(
        "video deleted",
        flush=True
    )



def main():

    url = get_video_url()


    clean_dir(
        OUTPUT_DIR
    )


    print(
        "STEP 1: download video",
        flush=True
    )

    download_video(url)



    print(
        "STEP 2: download subtitles",
        flush=True
    )

    download_subtitle(url)



    video = find_video()


    if not video:

        raise Exception(
            "video not found"
        )



    print(
        "STEP 3: screenshots",
        flush=True
    )

    extract_screenshots(video)



    print(
        "STEP 4: delete video",
        flush=True
    )

    delete_video()



    print(
        "DONE",
        flush=True
    )


if __name__ == "__main__":
    main()
