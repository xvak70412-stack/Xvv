import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "output"


def parse_body(body):
    m = re.search(r"(?im)^\s*url\s*:\s*(\S+)\s*$", body or "")
    if not m:
        raise ValueError("Issue body must contain URL: <youtube-url>")
    url = m.group(1)
    mode = re.search(r"(?im)^\s*mode\s*:\s*(auto|native|script)\s*$", body or "")
    images = re.search(r"(?im)^\s*images\s*:\s*(\d+)\s*$", body or "")
    return url, mode.group(1) if mode else "auto", min(15, max(1, int(images.group(1)))) if images else 15


def github_api(path):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
            "Accept": "application/vnd.github+json",
            "User-Agent": "Xvv-video-harness",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    print("START github_job_windows")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    print("EVENT KEYS:", list(event.keys()))

    repo = os.environ["GITHUB_REPOSITORY"]
    number = int(event.get("issue", {}).get("number", 0))
    if not number:
        raise ValueError("No issue number found in GitHub event")

    issue = github_api(f"/repos/{repo}/issues/{number}")
    url, mode, images = parse_body(issue.get("body", ""))

    out = OUT_ROOT / f"github-job-{number}"
    out.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, str(ROOT / "scripts" / "run-vlog-windows.py"), url, str(images), mode, "--out", str(out)]
    print("RUN:", cmd)
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    print(p.stdout)
    print(p.stderr)
    if p.returncode:
        raise SystemExit(p.returncode)


if __name__ == "__main__":
    main()
