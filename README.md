# agent-sync

Lean personal skill and agent instruction repository, wired directly into local harnesses via Windows NTFS junctions.

## Layout

- `AGENTS.md` — Shared behavioral rules (verification, Git-first workflow, workspace hygiene).
- `skills/<name>/SKILL.md` — Reusable workflow skills shared across hosts.
- `overrides/<model>.md` — Model-specific operational guardrails (`neon.md`, `codex.md`).
- `setup-links.ps1` — Idempotent Windows script that wires:
  - `~/.agents/skills` -> `skills/` (NTFS junction)
  - `~/.gemini/config/skills` -> `skills/` (NTFS junction)
  - `~/.gemini/config/AGENTS.md` and `~/.t3/userdata/providers/antigravity/*/config/AGENTS.md` <- composed from `AGENTS.md` + `overrides/neon.md`
  - (Optional `-IncludeCodex`: composes `AGENTS.md` + `overrides/codex.md` into `~/.codex/AGENTS.md`)

## Usage

Run once (or anytime you edit `AGENTS.md` / `overrides/*.md`, or a harness directory resets):

```powershell
.\setup-links.ps1
```

Edits under `skills/` take effect immediately via NTFS junctions; re-run `.\setup-links.ps1` after editing `AGENTS.md` or `overrides/*.md` to refresh the composed harness instruction files.

## History

Pre-reboot harness tooling and meta-skills are preserved at Git tag `archive/codex-era-2026`.
