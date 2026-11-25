# Shared Agent Rules

Universal behavioral rules for coding, research, and repo maintenance across hosts. Put workflow procedures in `skills/<name>/SKILL.md` and model-specific quirks in `overrides/<model>.md`.

## Verification & Rigor
- Verify every claim, fix, and build with actual command or test output before reporting completion; never guess or fill in unprinted results.
- Cite only observed file paths, symbols, and outputs. Flag any untested path or remaining gap explicitly.
- Optimize for total system cost rather than local patches. Challenge assumed constraints, outdated scaffolding, and redundant ceremony before adding new machinery.

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

<!-- temp-pref:t3code-pr-16532 -->
## Temporary Delegation Preference (until `pingdotgg/t3code#16532` merges)
- When running under Antigravity/Neon in T3 Code and a task requires controlling the user's already-open local Chrome (signed-in browser tabs) or desktop computer use, delegate that step via `delegate_task` to `providerInstanceId: "codex"`, model `gpt-6.2-sol` (current Codex Sol model; `gpt-6.1-sol` is no longer in the Codex catalog), with `options: { serviceTier: "priority" }` (fast mode). Use T3 Preview (`preview_*`) for ordinary browser work that does not need local Chrome or desktop CUA.
- Auto-remove this block once `https://github.com/pingdotgg/t3code/pull/16532` is merged.
<!-- /temp-pref:t3code-pr-16532 -->
