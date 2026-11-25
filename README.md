# agent-sync

Lean personal skill and agent instruction repository, wired directly into local harnesses via Windows NTFS junctions.

## Layout

- `AGENTS.md` — Shared behavioral rules (verification, Git-first workflow, workspace hygiene).
- `skills/<name>/SKILL.md` — Reusable workflow skills shared across hosts.
- `overrides/<model>.md` — Model-specific operational guardrails (`neon.md`, `codex.md`).
- `setup-links.ps1` — Idempotent Windows script that wires:
  - `~/.agents/skills` -> `skills/` (NTFS junction)
  - `~/.gemini/config/skills` -> `skills/` (NTFS junction)
  - `~/.gemini/config/AGENTS.md` -> `AGENTS.md` (hardlink)

## Usage

Run once (or anytime a harness directory resets):

```powershell
.\setup-links.ps1
```

Edits under `skills/` and `AGENTS.md` take effect immediately across all linked hosts without copying or sync daemons.

## History

Pre-reboot harness tooling and meta-skills are preserved at Git tag `archive/codex-era-2026`.
