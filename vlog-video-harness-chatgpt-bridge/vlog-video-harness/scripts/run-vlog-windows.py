import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd, cwd):
    print("\nRUN:", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def ytdlp_cmd(*args):
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp"
    ]

    cookies = Path("C:/actions-runner/secrets/cookies.txt")

    if cookies.is_file():
        cmd += [
            "--cookies",
            str(cookies)
        ]

    return [*cmd, *args]


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("url")
    parser.add_argument("images", type=int)
    parser.add_argument(
        "mode",
        choices=["auto", "native", "script"]
    )

    parser.add_argument(
        "--out",
        required=True
    )

    args = parser.parse_args()


    root = Path(__file__).resolve().parents[1]

    job = Path(args.out).resolve()

    py = sys.executable


    # 创建输出目录

    for folder in [
        "source",
        "subtitles",
        "frames"
    ]:
        (job / folder).mkdir(
            parents=True,
            exist_ok=True
        )


    # -------------------------
    # 1. 下载视频
    # -------------------------

    print("\nSTEP 1: Download video", flush=True)


    run(
        ytdlp_cmd(
            "--no-playlist",

            # 限制1080p，避免超大文件
            "-f",
            "bv*[height<=1080]+ba/b",

            "--merge-output-format",
            "mp4",

            "-o",
            str(
                job /
                "source" /
                "video.%(ext)s"
            ),

            args.url
        ),
        root
    )


    print("Video downloaded", flush=True)



    # -------------------------
    # 2. 下载字幕
    # -------------------------

    print("\nSTEP 2: Download subtitles", flush=True)


    run(
        ytdlp_cmd(
            "--no-playlist",

            "--write-subs",

            "--write-auto-subs",

            "--sub-langs",
            "zh.*,en.*",

            "--sub-format",
            "vtt",

            "--skip-download",

            "-o",
            str(
                job /
                "subtitles" /
                "%(id)s.%(ext)s"
            ),

            args.url
        ),
        root
    )


    subtitle_files = list(
        (job / "subtitles").glob("*.vtt")
    )


    print(
        "Subtitle files:",
        subtitle_files,
        flush=True
    )



    # -------------------------
    # 3. 截取截图
    # -------------------------

    print("\nSTEP 3: Generate screenshots", flush=True)


    videos = list(
        (job / "source").glob("*.mp4")
    )


    if not videos:
        raise RuntimeError(
            "No video file found"
        )


    video = videos[0]


    run(
        [
            py,

            str(
                root /
                "scripts" /
                "sample_frames.py"
            ),

            str(video),

            str(
                job /
                "frames"
            ),

            "--count",

            str(args.images)
        ],

        root
    )


    print(
        "Screenshots generated",
        flush=True
    )



    # -------------------------
    # 4. 删除视频
    # -------------------------

    print("\nSTEP 4: Delete temporary video", flush=True)


    if video.exists():

        video.unlink()

        print(
            "Deleted:",
            video,
            flush=True
        )



    print("\n===================")
    print("DONE")
    print("Frames:", job / "frames")
    print("Subtitles:", job / "subtitles")
    print("===================")



if __name__ == "__main__":
    main()
