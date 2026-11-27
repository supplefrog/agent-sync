# Shared Agent Rules

Universal preferences across hosts.

## Git-First Workflow
- Rely on Git for version history. Never create `.bak` files or pre-edit backup directories.
- On `agent-sync` and the user's personal repositories when asked to make changes, commit cleanly and push directly to `main` (or the active working branch) without asking for repeated confirmation; re-run `.\setup-links.ps1` only after editing `AGENTS.md` or `overrides/*.md`.
- Respect upstream contribution rules (`CONTRIBUTING.md`) on external repos; check for existing PRs/issues before opening new ones.

## Workspace Hygiene
- Clean up temporary scratch files, build leftovers, and auto-created helper/scratch threads once their work completes.
- Never leave orphaned worktrees, temp clones, or untracked artifacts inside checked-out repositories.

## Skills & Overrides (`C:\Users\E\Documents\Projects\agent-sync`)
- Put reusable skills in `skills/<name>/SKILL.md` (lean, with only the supporting scripts or references they actively need) rather than per-project folders unless project-specific.
- Put universal rules in `AGENTS.md` and model- or harness-specific guidance in `overrides/<model>.md`, then re-run `.\setup-links.ps1`.

## Model & Delegation Preferences
- **Codex fast mode:** Whenever delegating to or configuring OpenAI Codex (`codex` / `gpt-6.2-sol`) in T3 Code, default to fast mode (`options: { serviceTier: "priority" }`) unless explicitly asked for standard/default speed.

## Interactive Visual Controls
- **Give interactive elements for subjective visual tuning:** Across visual design and grading work—videos, frames, images, and webpage/UI dev views—when a visual choice is unresolved or repeated tweaks aren't landing, provide a compact interactive preview (inline HTML/Canvas or dev-view panel) with live labelled controls rather than guessing blindly across slow renders. Match pro Photoshop/video-editing ergonomics: include **interactive curves** (RGB/luma tone curves, hue-vs-sat/lum curves) alongside sliders, toggles, before/after split wipe, magnification, reset, and copyable exact parameters wired 1:1 to the render pipeline. Support fluidly moving between broad sweeping adjustments and minute tweaks wherever attention goes without forcing a rigid sequence.
