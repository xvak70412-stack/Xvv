"""Compare bounded reads of the same signed stream on the Windows runner."""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
import yt_dlp
from yt_dlp.networking import Request
import github_job_windows as job

LIMIT = 65536

class QuietLogger:
    def debug(self, message): pass
    def warning(self, message): pass
    def error(self, message): pass

def main():
    report = {"video": "3WMuzhQXJoY", "read_limit_bytes": LIMIT}
    remote = job.get_remote_video("https://www.youtube.com/watch?v=3WMuzhQXJoY")
    headers = dict(remote["headers"])
    report["format"] = remote["info"].get("format_id")
    report["protocol"] = remote["info"].get("protocol")
    report["headers_present"] = sorted(headers)
    report["stream_cookie_present"] = bool(headers.get("Cookie"))
    report["shared_proxy"] = bool(remote["proxy"])
    options = dict(remote["options"], logger=QuietLogger())
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            with ydl.urlopen(Request(remote["url"], headers=dict(headers, Range="bytes=0-65535"))) as response:
                data = response.read(LIMIT)
                report["yt_dlp"] = {"status": getattr(response, "status", None), "bytes": len(data), "ok": bool(data)}
    except Exception as error:
        report["yt_dlp"] = {"ok": False, "error_type": type(error).__name__, "status": getattr(error, "status", getattr(error, "code", None))}
    header_block = "".join(f"{k}: {v}\r\n" for k,v in headers.items()
                           if "\r" not in str(k)+str(v) and "\n" not in str(k)+str(v))
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-rw_timeout", "30000000"]
    if remote["proxy"]:
        cmd += ["-http_proxy", remote["proxy"]]
    if header_block:
        cmd += ["-headers", header_block]
    env = os.environ.copy()
    for key in list(env):
        if key.lower() in ("http_proxy", "https_proxy", "all_proxy"):
            env.pop(key)
    if remote["proxy"]:
        env["http_proxy"] = env["https_proxy"] = remote["proxy"]
    with tempfile.TemporaryDirectory(prefix="video-stream-probe-") as folder:
        target = Path(folder) / "probe.bin"
        # Raw data demuxer avoids codec parsing; limit the HTTP range and output.
        cmd += ["-start_offset", "0", "-end_offset", str(LIMIT),
                "-f", "data", "-i", remote["url"], "-map", "0:0",
                "-c", "copy", "-fs", str(LIMIT), "-f", "data", str(target)]
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                    env=env, timeout=45)
            size = target.stat().st_size if target.exists() else 0
            report["ffmpeg"] = {"ok": result.returncode == 0 and size > 0,
                                "exit_code": result.returncode, "bytes": size}
            if result.returncode:
                report["ffmpeg"]["diagnostic"] = job.ffmpeg_error(result.stderr, remote)
        except subprocess.TimeoutExpired:
            report["ffmpeg"] = {"ok": False, "error_type": "TimeoutExpired"}
    report["comparison"] = (
        "Both clients can read this stream" if report["yt_dlp"]["ok"] and report["ffmpeg"]["ok"]
        else "yt-dlp can read; FFmpeg cannot" if report["yt_dlp"]["ok"]
        else "FFmpeg can read; yt-dlp cannot" if report["ffmpeg"]["ok"]
        else "Neither client can read this stream")
    print("STREAM_PROBE_RESULT=" + json.dumps(report, ensure_ascii=False), flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as output:
            output.write("## Video stream comparison\n\n```json\n" + json.dumps(report, indent=2) + "\n```\n")

if __name__ == "__main__":
    main()
