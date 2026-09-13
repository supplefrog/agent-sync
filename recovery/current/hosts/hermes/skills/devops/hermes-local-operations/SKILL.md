---
name: hermes-local-operations
description: "Operate and troubleshoot the user’s live local Hermes Agent installation: inspect effective config/version/process state, updates, sessions, tools, voice, Windows/WSL boundaries, and installed-runtime behavior. Load hermes-agent for official commands and use this skill for local operational traps and reference routing. Use hermes-desktop-operations for Electron/Desktop-specific failures."
version: 2.0.3
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [hermes, local, operations, windows, wsl]
    related_skills: [hermes-agent, hermes-self-engineering, hermes-desktop-operations]
---

# Hermes Local Operations

Use this for real local Hermes maintenance. Inspect the live installation, make the smallest supported change, and verify from the process/shell the user actually runs.

The body is intentionally an index. Load only the reference relevant to the current failure instead of injecting years of accumulated local notes into every Hermes operation.

## Current environment boundary

For this user:

- Windows-native Hermes Desktop/CLI is canonical.
- The default profile is the only active Hermes profile unless the user explicitly creates another.
- WSL openSUSE is retained for unrelated GSD/external-agent state, not as a second Hermes brain.
- The terminal tool uses Git Bash/MSYS semantics on Windows; PowerShell commands must be invoked through `powershell.exe`.

Verify these facts live when they control an action. Do not infer the active home/runtime from an old path or session.

## Core workflow

1. Load `hermes-agent` for current official commands and consult official docs when behavior may have changed.
2. Identify the active runtime:
   - `hermes --version`
   - `hermes config path`
   - `hermes status --all`
   - process command lines when multiple launchers/backends may exist.
3. Inspect effective config and the exact failing surface before editing.
4. Prefer supported CLI/config/plugin paths over installed-source patches.
5. Keep Windows and WSL homes, runtimes, Node toolchains, and auth stores distinct.
6. Make reversible scoped changes without accumulating backups. For reproducible package upgrades, use the rollback lifecycle in `references/package-upgrades.md`; unique user data and conversation state remain protected.
7. Verify in the relevant fresh process when config, PATH, startup, provider, or tool discovery changed.
8. Report exact commands/results and any restart/reset requirement.

## Route to the owning workflow

- **Behavior/style/skills/model routing/prompt changes:** `hermes-self-engineering`.
- **Electron/Desktop renderer, session worker, composer, browser discovery, or dashboard backend:** `hermes-desktop-operations`.
- **Source bug that should survive updates:** `github-pr-workflow`.
- **Subagent route benchmarking:** `hermes-model-routing-evals` and `delegation-workflows`.
- **PowerShell completion:** `powershell-cli-completion-engineering`.
- **Whole compression-lineage deletion:** `hermes-compression-tree-delete`.
- **Old generated backups/snapshots/stashes:** `hermes-stale-artifact-cleanup`.

Do not duplicate those workflows here.

## Operational reference map

Load a reference only when its trigger matches.

### Config, prompt, tools, and routing

- `references/soul-and-personality-configuration.md` — concrete locations and config commands after the behavior surface has been selected.
- `references/tool-search-progressive-disclosure.md` — determine whether core Tool Search can actually defer any active plugin/MCP schemas.
- `references/auxiliary-model-efficiency.md` — auxiliary slots and benchmark criteria; live-check model availability.
- `references/profile-context-management.md` — historical profile/tool-budget patterns; use only if profiles are deliberately reintroduced.

### Updates and installed runtime

- [Package upgrades](references/package-upgrades.md) — provenance-aware skill/plugin inventory, capability-preserving upgrades, local-delta merges, regression checks, and retirement of obsolete copies.
- `references/hermes-update-performance.md` — updater phases, autostash semantics, shallow divergence, locks, and verification.
- `references/hermes-wsl-operations.md` — WSL-native Node/npm and Windows PATH leakage when operating a WSL runtime.
- `references/windows-host-tooling-from-wsl.md` — invoke Windows-authenticated tools from WSL when that environment is intentionally in use.

Do not run updates, dependency installs, or rebuilds while active Desktop/TUI workers are doing user work unless interruption was explicitly requested.

### Voice/STT/TTS

- `references/hermes-local-stt-provider-and-quantization.md`
- `references/hermes-voice-mode-wsl.md`
- `references/hermes-voice-default-cleanup.md`
- `references/hermes-tui-windows-terminal.md`

Identify the actual frontend and Hermes runtime venv before changing packages. Codex OAuth is not an OpenAI Speech API key.

### Sessions and state

- For relocating project folders and preserving old Desktop threads, load `references/workspace-relocation.md`.

- `references/session-compression-lineage-cleanup.md` — lineage-aware cleanup rather than deleting a visible continuation only.
- `references/session-cleanup-achievement-preservation.md` — only when achievements are installed and historical evidence matters.

The active Windows `state.db` is authoritative unless `hermes config path` proves otherwise. Do not import stale WSL sessions when the user asked to delete legacy copies.

## Windows/WSL rules

- Construct Windows paths from the known user home, not hostname output.
- Git Bash/MSYS can rewrite `/root/...` arguments passed to `wsl.exe`; use a temp script plus `MSYS2_ARG_CONV_EXCL='*'` for sensitive WSL operations.
- Inspect command resolution before package/tool repairs. Windows Node shims leaking into WSL are a PATH problem, not proof Node is broken.
- Probe the Python from the `hermes` shebang/venv, not arbitrary system Python.
- Do not treat `/root/.agents` as Hermes clutter; retained GSD uses it.
- Never print `.env`, auth tokens, or credential values. Presence and key names are enough.

## Verification patterns

- **Config:** read back with `hermes config`/`config check`, then use a fresh session if snapshotted at startup.
- **PATH/tool discovery:** verify `command -v`/`where.exe`, version, and the real consuming process.
- **Session DB:** query exact rows/counts, then confirm through Hermes sessions/search UI.
- **Update repair:** clean git state, expected head, no stale lock/stash, version, and config check.

## Pitfalls

- `provider: auto` is predictable fallback behavior, not a cost optimizer.
- A model appearing in a catalog is not proof the account can call it.
- Local installed-tree patches are update-fragile; upstream them or remove them.
- Do not preserve transient failures as permanent skill rules. Keep reusable diagnosis and verification mechanisms only.
