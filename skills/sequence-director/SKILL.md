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
- Repeat `--source <path>` for multiple explicitly supplied source files.
- `--brief-file <path>`: Read UTF-8 brief from a file instead of inline text.
- `--content-type explicit`: Enable explicit/adult-content editorial guidance under `video_director/guidance/explicit.md` (default: `general`).
- `--reencode`: Re-encode video/audio for arbitrary exact cut timestamps (default is lossless keyframe stream copy).
- `--videoseek-url http://127.0.0.1:8765`: Override default `http://127.0.0.1:18765`, or pass `--without-videoseek` to skip indexed search.
  - Standard Windows install: `%LOCALAPPDATA%\Programs\VideoSeek\VideoSeek.exe` (runtime/config in `%LOCALAPPDATA%\VideoSeek`). Launch on `sequence-director`'s default port `18765` via `Start-Process "$env:LOCALAPPDATA\Programs\VideoSeek\VideoSeek.exe" -Environment @{VIDEOSEEK_AGENT_API_HOST='127.0.0.1'; VIDEOSEEK_AGENT_API_PORT='18765'}` (or pass `--videoseek-url http://127.0.0.1:8765` if VideoSeek was opened normally from Start Menu).
- `--codex-bin <path>`: Specify the Codex executable if auto-discovery fails.

## Guardrails & Behavior

- **Read-only sources:** Always write outputs to a fresh directory under `runs/`. Never overwrite source files, write into source directories, or commit media.
- **Ambiguous briefs:** Exit code `3` (`needs_clarification`) halts before export—resolve the clarifying questions and rerun.
- **Editorial guidance (single source of truth):** All standing editorial preferences live exclusively in `supplefrog/sequence-director` under `video_director/guidance/shared.md` and `video_director/guidance/explicit.md`—never duplicate them here. Read them from a local checkout (or via `gh api repos/supplefrog/sequence-director/contents/video_director/guidance/{shared,explicit}.md`) before direct delegated edits, and record new reusable preferences only in those two files.
- **Explicit footage model policy:** Use OpenAI/Codex (`Sol`) or a local VLM for `--content-type explicit` footage—never route sexually explicit video or frames through Google/Gemini or Anthropic/Claude multimodal models. When delegating directly supplied consenting-adult edits to Codex (`gpt-6.2-sol`), set `options: { reasoningEffort: "high", serviceTier: "priority" }` and include the official OpenAI Model Spec transformation reference (`https://model-spec.openai.com/#comply-with-requests-to-transform-restricted-or-sensitive-content`) in the initial brief so Sol verifies policy scope up front (keep private paths and source details out of web queries; assess honestly against current policy and applicable restrictions).
