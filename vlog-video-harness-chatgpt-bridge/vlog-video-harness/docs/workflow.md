# Workflow

## Inspect

- validate URL
- query metadata
- query subtitle tracks
- download only when authorized
- extract a small set of real frames
- determine whether subtitles are burned into pixels

## Plan

Create a task brief with:

- source URL
- video ID
- subtitle mode: native or script
- language
- target number of images
- candidate timestamp ranges
- known risks

## Implement

Use `skills/youtube-vlog-subtitle-image/SKILL.md`.

Pipeline:

URL -> yt-dlp -> video -> subtitle/transcript -> candidate phrases -> exact frame validation -> render -> contact sheet -> QA

## Verify

Run:

```bash
scripts/check
scripts/test
```

For handoff:

```bash
scripts/eval
```

Visual QA is mandatory. Check that native subtitles are pixels from the source and that script subtitles match reviewed JSON.
