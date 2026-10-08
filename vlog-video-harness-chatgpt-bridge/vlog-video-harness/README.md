# Vlog Video Harness — ChatGPT Bridge Edition

This edition adds a B-mode bridge: ChatGPT creates a GitHub `video-job` issue, GitHub Actions dispatches the job to your self-hosted machine, and the existing yt-dlp/FFmpeg pipeline produces the quote images.

## Local direct mode

```bash
scripts/bootstrap
scripts/doctor
scripts/run-vlog "https://www.youtube.com/watch?v=vNi4RUQrvy4"
```

## ChatGPT bridge mode

See `docs/chatgpt-bridge.md`.

The intended interaction becomes:

```text
User: https://www.youtube.com/watch?v=...
ChatGPT: submit video job
GitHub: queue
Your machine: download + analyze + render
GitHub: artifact + result comment
ChatGPT: inspect result and continue QA
```

The bridge does not claim that VTT subtitles are burned into the pixels. Native subtitle mode still requires visual confirmation.
