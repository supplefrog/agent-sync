# Shared Agent Rules

Universal preferences across hosts. Put workflow procedures in `skills/<name>/SKILL.md` and harness/model-specific rules in `overrides/<model>.md`.

## Git-First Workflow
- Rely on Git for version history. Never create `.bak` files or pre-edit backup directories.
- On `agent-sync` and the user's personal repositories when asked to make changes, commit cleanly and push directly to `main` (or the active working branch) without asking for repeated confirmation or running custom wrapper sync scripts.
- Respect upstream contribution rules (`CONTRIBUTING.md`) on external repos; check for existing PRs/issues before opening new ones.

## Workspace Hygiene
- Clean up temporary scratch files, build leftovers, and auto-created helper/scratch threads once their work completes.
- Never leave orphaned worktrees, temp clones, or untracked artifacts inside checked-out repositories.

## Skills & Overrides Layout
- Keep `skills/` lean: each skill lives in `skills/<name>/SKILL.md` with only the supporting scripts or references it actively needs.
- Keep model- or harness-specific guidance isolated under `overrides/<model>.md` so universal instructions stay small and portable.
