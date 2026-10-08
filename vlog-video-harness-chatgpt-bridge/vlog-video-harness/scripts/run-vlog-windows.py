import argparse, json, subprocess, sys
from pathlib import Path

def run(cmd, cwd):
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=True)

def ytdlp_cmd(*args):
    return [sys.executable, "-m", "yt_dlp", *args]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("images", type=int)
    ap.add_argument("mode", choices=["auto", "native", "script"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    job = Path(a.out).resolve()
    py = sys.executable

    for n in ("source", "subtitles", "frames", "candidates", "final"):
        (job / n).mkdir(parents=True, exist_ok=True)

    run([
        py, str(root / "scripts" / "video_pipeline.py"), a.url,
        "--out", str(job / "source" / "metadata.json")
    ], root)

    run(ytdlp_cmd(
        "--no-playlist", "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "-o", str(job / "source" / "video.%(ext)s"), a.url
    ), root)

    # YouTube may require an authenticated browser session for subtitle tracks.
    # First record the subtitle tracks yt-dlp can actually see, then download them.
    env = None
    subtitle_log = job / "subtitles" / "ytdlp-subs.txt"

    list_cmd = ytdlp_cmd(
        "--no-playlist",
        "--cookies-from-browser", "chrome",
        "--list-subs",
        a.url
    )
    print("+", " ".join(map(str, list_cmd)), flush=True)
    listed = subprocess.run(
        list_cmd, cwd=root, text=True, capture_output=True
    )
    subtitle_log.write_text(
        "=== yt-dlp --list-subs ===\n"
        + listed.stdout
        + "\n=== STDERR ===\n"
        + listed.stderr,
        encoding="utf-8",
    )
    print(listed.stdout, end="", flush=True)
    print(listed.stderr, end="", file=sys.stderr, flush=True)

    subtitle_cmd = ytdlp_cmd(
        "--no-playlist",
        "--sleep-requests", "1",
        "--cookies-from-browser", "chrome",
        "--write-subs", "--write-auto-subs",
        "--sub-langs", "zh.*,en.*,ja.*,ko.*",
        "--sub-format", "vtt",
        "--skip-download",
        "-o", str(job / "subtitles" / "%(id)s.%(ext)s"),
        a.url,
    )
    run(subtitle_cmd, root)

    subtitle_files = sorted(job.joinpath("subtitles").glob("*.vtt"))
    if not subtitle_files:
        raise RuntimeError(
            "No VTT subtitle files were downloaded. "
            f"See {subtitle_log} for the exact yt-dlp subtitle-track response."
        )

    (job / "subtitles" / "subtitle-summary.json").write_text(
        json.dumps(
            {
                "count": len(subtitle_files),
                "files": [p.name for p in subtitle_files],
                "list_subs_returncode": listed.returncode,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    videos = list((job / "source").glob("*.mp4"))
    if not videos:
        raise RuntimeError("No MP4 video found")
    video = videos[0]

    run([
        py, str(root / "scripts" / "sample_frames.py"),
        str(video), str(job / "frames"), "--count", "48"
    ], root)

    run([
        py, str(root / "scripts" / "analyze_candidates.py"),
        str(video), str(job / "subtitles"),
        "--images", str(a.images), "--mode", a.mode,
        "--out", str(job / "candidates" / "manifest.json")
    ], root)

    run([
        py, str(root / "scripts" / "render_3x4.py"),
        str(video), str(job / "candidates" / "manifest.json"),
        "--out", str(job / "final"), "--width", "1440"
    ], root)

    run([
        py, str(root / "scripts" / "qa.py"),
        "--output", str(job / "final")
    ], root)

if __name__ == "__main__":
    main()
