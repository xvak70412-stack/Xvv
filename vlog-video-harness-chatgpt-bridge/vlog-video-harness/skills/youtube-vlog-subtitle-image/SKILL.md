---
name: youtube-vlog-subtitle-image
description: Orchestrate an authorized YouTube/local Vlog into verified 3:4 quote images using real video frames, with strict native-vs-script subtitle separation.
---

# YouTube Vlog Subtitle Image

## Input

Accept:
- YouTube URL
- local MP4/MOV/WebM

Default URL:
`https://www.youtube.com/watch?v=vNi4RUQrvy4`

## Stage 0 — Access gate

Before downloading:
1. confirm the user is authorized to process the source;
2. use yt-dlp only through normal access;
3. never bypass DRM/paywalls/access controls;
4. if authentication is required, stop and ask the user to provide an authorized local file or explicitly authorize an appropriate browser-cookie workflow.

## Stage 1 — Inspect

Run metadata and subtitle discovery:

```bash
yt-dlp --no-playlist --dump-single-json --skip-download "$URL"
yt-dlp --no-playlist --list-subs "$URL"
```

If permitted:

```bash
yt-dlp --no-playlist \
  -f "bv*+ba/b" --merge-output-format mp4 \
  -o "source/%(id)s.%(ext)s" "$URL"
```

Acquire subtitle tracks for analysis only. They do not prove that subtitles are burned into pixels.

## Stage 2 — Determine subtitle mode

Inspect real frames.

### Native mode

Use only when the subtitle remains visible with player CC disabled.

Rules:
- subtitle text must come from video pixels;
- do not OCR and redraw;
- do not translate;
- do not rewrite;
- preserve original subtitle geometry as much as possible.

### Script mode

Use only when the user accepts post-production text.

Rules:
- text comes from reviewed `lines.json`;
- clearly label output as post-production subtitles;
- never claim it is a native quote.

If native was requested but no burned subtitle exists, stop and request permission to switch modes.

## Stage 3 — Select content

Prefer a continuous thought with:
- 4–6 useful lines;
- strong visual subject;
- readable subtitles;
- stable frames;
- meaningful progression.

Avoid:
- empty/duplicate captions;
- transition frames;
- player UI;
- severe motion blur;
- closed eyes or cropped faces;
- unrelated lines stitched together only to fill a template.

Use subtitle timestamps to find candidates, then verify each candidate against real frames.

## Stage 4 — Render

Default:
- 3:4
- 1440x1920
- one hero frame + four subtitle strips
- zero gap between strips
- do not stretch faces
- native mode: crop source pixels and scale once after assembly

If the upstream `native-subtitle-quote-image` Skill is installed, delegate rendering to it:

```text
使用 $native-subtitle-quote-image，读取当前任务的 video + manifest，
按 native/script 模式渲染并输出 contact sheet。
```

Otherwise use its scripts directly if copied into this repository.

## Stage 5 — QA

For every output verify:
1. timestamp order;
2. subtitle completeness;
3. native text was not redrawn;
4. script text exactly matches reviewed JSON;
5. no subtitle transition residue;
6. faces/subjects are not badly cropped;
7. no large meaningless blank space;
8. no player controls;
9. readable at thumbnail size;
10. output count matches manifests.

Create:
- JPG outputs
- timestamp/line manifest
- contact sheet
- `qa.md`

Do not report success merely because a command exited with code 0.

## Handoff

Report:
- source URL/video ID
- access status
- subtitle mode
- selected topics
- output files
- QA result
- unresolved risks
