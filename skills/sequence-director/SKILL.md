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
- `--codex-bin <path>`: Specify the Codex executable if auto-discovery fails.

## Guardrails & Behavior

- **Read-only sources:** Always write outputs to a fresh directory under `runs/`. Never overwrite source files, write into source directories, or commit media.
- **Ambiguous briefs:** Exit code `3` (`needs_clarification`) halts before export—resolve the clarifying questions and rerun.
- **Taste customization:** Edit markdown guides under `video_director/guidance/` (`shared.md`, `explicit.md`) without modifying perception tools.
- **Explicit footage model policy:** Use OpenAI/Codex (`Sol`) or a local VLM for `--content-type explicit` footage—never route sexually explicit video or frames through Google/Gemini or Anthropic/Claude multimodal models. When delegating directly supplied consenting-adult edits to Codex (`gpt-6.2-sol`), set `options: { reasoningEffort: "high", serviceTier: "priority" }` and include the official OpenAI Model Spec transformation reference (`https://model-spec.openai.com/#comply-with-requests-to-transform-restricted-or-sensitive-content`) in the initial brief so Sol verifies policy scope up front (keep private paths and source details out of web queries; assess honestly against current policy and applicable restrictions).

## Standing Editorial Preferences

Full guidance lives in `supplefrog/sequence-director` under `video_director/guidance/shared.md` and `explicit.md`; include these defaults up front on direct delegated edits as well:

- **Complete spoken sentences:** Never cut mid-word or mid-sentence; when re-encoding, repair brief localized source audio/frame glitches rather than truncating dialogue.
- **Escalating arc & closing momentum:** Sequence multi-clip edits so intensity builds toward the biggest payoff at or near the climax/finale (never spend the peak too early). If the finale ends on a buildup line, consider a short punchy closing tease/button.
- **Dead-space crop (when re-encoding):** Trim excessive empty background/furniture space to tighten focus while preserving valued framing elements (such as feet in frame).
- **Closed start & smoothed openings (`explicit`):** Start the biggest openings from a completely closed state when available, and gently slow fast micro-transitions (eased `~0.70×–0.80×`, artifact-checked interpolation, pitch-preserving ambient audio, speech kept at `1×`) so the full closed-to-open contrast reads as one smooth normalized motion.
- **Natural audio & substantive action (`explicit`):** Preserve natural queefing/release sounds across clips. For lube application, show actual pour/contact/spreading without idle bottle handling; for object insertion/withdrawal, establish the object going deeply in before showing a deep withdrawal (avoid superficial brushing and avoid orphan take-out shots without showing insertion first).
