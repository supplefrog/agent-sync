---
name: sequence-director
description: Use when editing supplied video footage into paced action sequences using supplefrog/sequence-director (Python + FFmpeg + optional VideoSeek).
---

# Sequence Director

Agent-directed video editor for explicitly supplied footage. Selects complete action sequences matching a clarified brief and exports lossless keyframe-aligned cuts (or re-encodes when exact non-keyframe cuts are requested).

## Locating the Repo

Check existing local checkouts first; otherwise clone:

```powershell
gh repo clone supplefrog/sequence-director
```

Requires Python 3.11+, Pillow (`pip install -r requirements.txt`), `ffmpeg`/`ffprobe` on `PATH`, and an active Codex CLI runtime (or `--codex-bin`).

## Standard Command

```powershell
python direct.py run --source "C:\path\video.mp4" --brief "Keep complete sequences showing the requested action." --output runs/new-edit
```

Key flags:
- `--brief-file <path>`: Read UTF-8 brief from a file instead of inline text.
- `--content-type explicit`: Enable explicit/adult-content editorial guidance under `video_director/guidance/explicit.md` (default: `general`).
- `--reencode`: Re-encode video/audio for arbitrary exact cut timestamps (default is lossless keyframe stream copy).
- `--videoseek-url http://127.0.0.1:8765`: Override default `http://127.0.0.1:18765`, or pass `--without-videoseek` to skip indexed search.
- `--codex-bin <path>`: Specify the Codex executable if auto-discovery fails.

## Guardrails & Behavior

- **Read-only sources:** Always write outputs to a fresh directory under `runs/`. Never overwrite source files, write into source directories, or commit media.
- **Ambiguous briefs:** Exit code `3` (`needs_clarification`) halts before export—resolve the clarifying questions and rerun.
- **Taste customization:** Edit markdown guides under `video_director/guidance/` (`shared.md`, `explicit.md`) without modifying perception tools.
- **Explicit footage model policy:** Use OpenAI/Codex (`Sol`) or a local VLM for `--content-type explicit` footage—never route sexually explicit video or frames through Google/Gemini or Anthropic/Claude multimodal models.
