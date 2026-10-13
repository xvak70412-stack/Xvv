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


def inspect_metadata(remote):
    import time
    from urllib.parse import urlsplit, parse_qs
    from urllib.request import proxy_bypass_environment
    from yt_dlp.version import __version__
    params = parse_qs(urlsplit(remote["url"]).query)
    def safe_client(value):
        return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_. -]{1,100}", value) else None
    def describe(info):
        query = parse_qs(urlsplit(info.get("url", "")).query)
        expiry = query.get("expire", [""])[0]
        return {
            "format": info.get("format_id"), "height": info.get("height"),
            "protocol": info.get("protocol"),
            "client": safe_client(query.get("c", [""])[0]),
            "extractor_client": safe_client(info.get("__yt_dlp_client")),
            "signature_present": any(query.get(key) for key in ("sig", "signature", "lsig")),
            "n_parameter_present": bool(query.get("n")),
            "po_token_present": bool(query.get("pot")),
            "ip_binding_present": bool(query.get("ip")),
            "expires_in_seconds": int(expiry) - int(time.time()) if expiry.isdigit() else None,
            "googlevideo_host": (urlsplit(info.get("url", "")).hostname or "").endswith(".googlevideo.com"),
        }
    info = remote["info"]
    report = {"yt_dlp_version": __version__, "selected": describe(info),
              "cookies_file_exists": Path(remote["options"].get("cookiefile", "")).is_file(),
              "matching_stream_cookie": bool(remote["headers"].get("Cookie")),
              "shared_proxy": bool(remote["proxy"]),
              "proxy_bypass_for_youtube": proxy_bypass_environment("www.youtube.com"),
              "proxy_bypass_for_video_host": proxy_bypass_environment(urlsplit(remote["url"]).hostname or ""),
              "formats": [describe(f) for f in info.get("formats", [])
                          if f.get("height") == 1080 and f.get("url")][:20]}
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    if "[response-headers]" in (event.get("issue", {}).get("body") or ""):
        options = dict(remote["options"], logger=QuietLogger())
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                with ydl.urlopen(Request(remote["url"], headers=remote["headers"], method="HEAD")) as response:
                    report["head_status"] = getattr(response, "status", None)
                    report["response_headers"] = {k: response.headers.get(k) for k in
                        ("Server", "Date", "Content-Type", "Content-Length") if response.headers.get(k)}
        except Exception as error:
            report["head_status"] = getattr(error, "status", getattr(error, "code", None))
            response = getattr(error, "response", None)
            hdrs = getattr(response, "headers", None)
            report["response_headers"] = {k: hdrs.get(k) for k in
                ("Server", "Date", "Content-Type", "Content-Length") if hdrs is not None and hdrs.get(k)}
            if response is not None:
                response.close()
        date = report.get("response_headers", {}).get("Date")
        if date:
            from email.utils import parsedate_to_datetime
            report["server_clock_difference_seconds"] = round(parsedate_to_datetime(date).timestamp() - time.time())
    print("STREAM_METADATA_RESULT=" + json.dumps(report, ensure_ascii=False), flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write("## Stream metadata diagnostics\n\n```json\n" + json.dumps(report, indent=2) + "\n```\n")


def main():
    report = {"video": "3WMuzhQXJoY", "read_limit_bytes": LIMIT}
    remote = job.get_remote_video("https://www.youtube.com/watch?v=3WMuzhQXJoY")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    if "[metadata-only]" in (event.get("issue", {}).get("body") or ""):
        inspect_metadata(remote)
        return
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
    headers["Range"] = "bytes=0-65535"
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
        cmd += ["-f", "data", "-i", remote["url"], "-map", "0:0",
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
