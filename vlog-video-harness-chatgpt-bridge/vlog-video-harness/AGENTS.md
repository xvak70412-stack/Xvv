# Vlog Video Harness Instructions

This repository is a Codex/agent harness for turning authorized YouTube URLs or local videos into verified 3:4 subtitle quote images.

## Commands

Run from repository root:

- `scripts/bootstrap`
- `scripts/doctor`
- `scripts/check`
- `scripts/test`
- `scripts/eval`

## Task loop

1. Inspect: inspect URL, access, metadata, subtitle availability and real frames.
2. Plan: decide subtitle mode and candidate selection strategy.
3. Implement: download/extract, select timestamps, render.
4. Verify: run structural checks and visual QA.
5. Handoff: report outputs, source, subtitle mode, verification and residual risks.

## Non-negotiable media rules

- Only process media the user is authorized to download/use.
- Never bypass DRM, paywalls, access controls or authentication.
- Never claim to have inspected frames that were not actually available.
- Native subtitles must come from video pixels. Do not OCR and redraw them.
- Script subtitles must come from reviewed JSON and must be identified as post-production text.
- A successful command is not sufficient evidence of visual quality; inspect the rendered contact sheet.

## Default target

If the user provides no URL, use:
`https://www.youtube.com/watch?v=vNi4RUQrvy4`

Default output:
- 3:4
- 1440x1920
- one hero frame + four subtitle strips
- JPG + manifest/timestamps + contact sheet + QA report
