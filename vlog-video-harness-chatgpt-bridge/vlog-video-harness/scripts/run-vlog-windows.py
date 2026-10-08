import argparse, os, shutil, subprocess, sys
from pathlib import Path

def run(cmd, cwd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)

def ytdlp_exe():
    py_path = os.environ.get("PYTHONPATH", "")
    for base in py_path.split(os.pathsep):
        if not base:
            continue
        root = Path(base)
        for candidate in (
            root / "bin" / "yt-dlp.exe",
            root / "Scripts" / "yt-dlp.exe",
            root / "yt-dlp.exe",
        ):
            if candidate.exists():
                return str(candidate)
    found = shutil.which("yt-dlp")
    if found:
        return found
    raise FileNotFoundError("yt-dlp executable not found in PATH or PYTHONPATH target")

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
    ytdlp = ytdlp_exe()

    for n in ("source", "subtitles", "frames", "candidates", "final"):
        (job / n).mkdir(parents=True, exist_ok=True)

    run([py, str(root / "scripts" / "video_pipeline.py"), a.url,
         "--out", str(job / "source" / "metadata.json")], root)

    run([ytdlp,
         "--no-playlist", "-f", "bv*+ba/b",
         "--merge-output-format", "mp4",
         "-o", str(job / "source" / "video.%(ext)s"), a.url], root)

    run([ytdlp,
         "--no-playlist",
         "--write-subs", "--write-auto-subs",
         "--sub-langs", "zh.*,en.*,ja.*,ko.*",
         "--sub-format", "vtt",
         "--skip-download",
         "-o", str(job / "subtitles" / "%(id)s.%(ext)s"), a.url], root)

    videos = list((job / "source").glob("*.mp4"))
    if not videos:
        raise RuntimeError("No MP4 video found")
    video = videos[0]

    run([py, str(root / "scripts" / "sample_frames.py"),
         str(video), str(job / "frames"), "--count", "48"], root)

    run([py, str(root / "scripts" / "analyze_candidates.py"),
         str(video), str(job / "subtitles"),
         "--images", str(a.images),
         "--mode", a.mode,
         "--out", str(job / "candidates" / "manifest.json")], root)

    run([py, str(root / "scripts" / "render_3x4.py"),
         str(video), str(job / "candidates" / "manifest.json"),
         "--out", str(job / "final"), "--width", "1440"], root)

    run([py, str(root / "scripts" / "qa.py"),
         "--output", str(job / "final")], root)

if __name__ == "__main__":
    main()
