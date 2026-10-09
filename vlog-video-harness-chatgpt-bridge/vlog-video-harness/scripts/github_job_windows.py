import argparse
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
        raise ValueError("Issue body must contain: URL: <youtube-url>")
    url = m.group(1)
    if not re.match(r"^https?://(www\.)?(youtube\.com|youtu\.be)/", url):
        raise ValueError("Only YouTube URLs are accepted")
    mm = re.search(r"(?im)^\s*mode\s*:\s*(auto|native|script)\s*$", body or "")
    mode = mm.group(1) if mm else "auto"
    im = re.search(r"(?im)^\s*images\s*:\s*(\d+)\s*$", body or "")
    images = max(1, min(10, int(im.group(1)))) if im else 5
    return url, mode, images

def github_api(path, method="GET", payload=None):
    token = os.environ["GITHUB_TOKEN"]
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.github.com" + path,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "Xvv-video-harness",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else {}

def comment(repo, issue, body):
    github_api(f"/repos/{repo}/issues/{issue}/comments", "POST", {"body": body})

def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    event_issue = event["issue"]
    number = int(event_issue["number"])
    repo = os.environ["GITHUB_REPOSITORY"]
    run_url = os.environ.get("GITHUB_RUN_URL", "")
    out = OUT_ROOT / f"github-job-{number}"
    out.mkdir(parents=True, exist_ok=True)
    try:
        # Fetch the latest issue body; reruns may contain an older event snapshot.
        issue = github_api(f"/repos/{repo}/issues/{number}")
        url, mode, images = parse_body(issue.get("body", ""))
        comment(
            repo,
            number,
            "## Video job\n\nStatus: running\n\nURL: " + url +
            "\n\nMode: " + mode + " · Images: " + str(images) +
            "\n\nRun: " + run_url,
        )
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "run-vlog-windows.py"),
            url,
            str(images),
            mode,
            "--out",
            str(out),
        ]
        p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
        result = {
            "status": "success" if p.returncode == 0 else "failed",
            "job": number,
            "url": url,
            "mode": mode,
            "images": images,
            "returncode": p.returncode,
            "stdout_tail": p.stdout[-6000:],
            "stderr_tail": p.stderr[-6000:],
            "output_dir": str(out),
        }
        (out / "job-result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        msg = (
            "## Video job result\n\nStatus: " + result["status"] +
            "\n\nMode: " + mode + " · Images: " + str(images) +
            "\n\nRun: " + run_url
        )
        if p.returncode:
            msg += "\n\nError tail:\n\n" + p.stderr[-4000:]
        comment(repo, number, msg)
        if p.returncode:
            raise SystemExit(p.returncode)
    except Exception as exc:
        (out / "job-result.json").write_text(
            json.dumps({"status": "failed", "job": number, "error": repr(exc)},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            comment(
                repo,
                number,
                "## Video job result\n\nStatus: failed\n\nError: " +
                repr(exc) + "\n\nRun: " + run_url,
            )
        except Exception:
            pass
        raise

if __name__ == "__main__":
    main()
