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


    try:

        run([
            "yt-dlp",

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


    print(
        "STEP 1 DOWNLOAD VIDEO",
        flush=True
    )

    download_video(url)



    print(
        "STEP 2 DOWNLOAD SUBTITLE",
        flush=True
    )

    download_subtitle(url)



    video = find_video()


    if not video:

        raise Exception(
            "video not found"
        )



    print(
        "STEP 3 SCREENSHOTS",
        flush=True
    )

    extract_screenshots(video)



    print(
        "STEP 4 DELETE VIDEO",
        flush=True
    )

    delete_video()



    show_output()


    print(
        "\nDONE",
        flush=True
    )



if __name__ == "__main__":

    main()
