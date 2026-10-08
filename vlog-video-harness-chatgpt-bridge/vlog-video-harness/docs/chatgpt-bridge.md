# ChatGPT → GitHub → Local Video Harness

This is the B architecture.

```text
ChatGPT
  │ creates GitHub issue labeled `video-job`
  ▼
GitHub
  │ issues.opened / labeled
  ▼
GitHub Actions
  │ self-hosted runner: `video-harness`
  ▼
Your computer
  │ yt-dlp + FFmpeg + vision/analysis tools
  ▼
output + GitHub Actions artifact
  │
  └── issue comment with status/run link
```

## One-time setup

1. Put this repository on GitHub.
2. Install a GitHub Actions **self-hosted runner** on the machine that has yt-dlp and FFmpeg.
3. Give the runner labels: `self-hosted`, `linux`, `video-harness` (adapt `runs-on` in the workflow for Windows/macOS).
4. Install the runtime requirements from `README.md` on that machine.
5. Enable the GitHub connection in ChatGPT for the repository you want to use.

## Submit a job from ChatGPT

Create/open an issue with the `video-job` label and this body:

```text
URL: https://www.youtube.com/watch?v=...
MODE: auto
IMAGES: 5
```

The workflow validates that the URL is YouTube before invoking yt-dlp.

## Why this is B instead of ordinary web browsing

The ChatGPT side handles orchestration and job creation. The self-hosted runner performs the bandwidth-heavy and executable work: downloading the media, decoding frames, running FFmpeg and producing artifacts. ChatGPT never needs direct access to your local filesystem or network.

## Security notes

- Use a private repository if the outputs are private.
- Keep the self-hosted runner dedicated to this workload.
- Do not accept arbitrary shell commands from issue bodies.
- The bridge accepts only YouTube URLs and fixed mode/image fields.
- Review GitHub Actions permissions before enabling write access.
