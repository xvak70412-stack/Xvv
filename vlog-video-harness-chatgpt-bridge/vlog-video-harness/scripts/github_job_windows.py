import os
import json
import subprocess
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "outputs"

VIDEO_DIR = OUTPUT_DIR / "video"
IMAGE_DIR = OUTPUT_DIR / "screenshots"
SUBTITLE_DIR = OUTPUT_DIR / "subtitles"


def run(cmd):
    print("\n>>>", " ".join(cmd))
    subprocess.run(cmd, check=True)


def clean_dir(path):
    if path.exists():
        shutil.rmtree(path)

    path.mkdir(parents=True, exist_ok=True)


def download_video(url):
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    output = VIDEO_DIR / "source.%(ext)s"

    run([
        "yt-dlp",
        "-f",
        "bestvideo+bestaudio/best",
        "-o",
        str(output),
        url
    ])


def download_subtitle(url):
    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)

    output = SUBTITLE_DIR / "subtitle"

    run([
        "yt-dlp",
        "--write-auto-subs",
        "--write-subs",
        "--sub-lang",
        "zh,en",
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

    # 15张截图
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

        print("video deleted")


def main():

    url = os.environ.get(
        "VIDEO_URL"
    )

    if not url:
        raise Exception(
            "missing VIDEO_URL"
        )


    clean_dir(OUTPUT_DIR)

    print("download video")

    download_video(url)


    print("download subtitles")

    download_subtitle(url)


    video=find_video()

    if not video:
        raise Exception(
            "video not found"
        )


    print("extract screenshots")

    extract_screenshots(video)


    print("remove video")

    delete_video()


    print("DONE")


if __name__ == "__main__":
    main()
