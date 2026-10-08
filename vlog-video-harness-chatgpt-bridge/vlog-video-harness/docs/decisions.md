# Decisions

## 2026-10-08

- Harness is intentionally language-agnostic and follows the stable command contract from Harness-for-codex.
- Media processing is isolated in a Skill so the harness can orchestrate it without embedding every video-specific procedure in AGENTS.md.
- YouTube acquisition uses yt-dlp and must respect access permissions.
- Native and script subtitle modes are mutually exclusive.
- Visual QA is a handoff gate, not an optional postscript.
