---
name: hermes-desktop-operations
description: "Operate and troubleshoot Hermes Desktop on Windows: Electron/dashboard backend ownership, process trees, session resume/state, renderer/composer behavior, updates, browser CLI discovery, Windows/WSL migration, and installed-runtime behavior. Use only for Desktop-specific behavior; use hermes-local-operations for general CLI/config operations."
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [hermes, desktop, windows, electron, troubleshooting]
    related_skills: [hermes-agent, hermes-local-operations, github-pr-workflow]
---

# Hermes Desktop Operations

Treat Desktop as an Electron frontend plus a Hermes dashboard backend and per-session workers. UI symptoms, backend state, persisted session rows, and stale processes are separate layers; inspect them before changing config or source.

This skill is a compact router to detailed references. Load only the reference matching the symptom.

## Current architecture checkpoint

On this setup, verify but expect:

- Hermes home/state: `{{agent-signal:HERMES_HOME}}`
- integrated source/runtime: `%LOCALAPPDATA%\hermes\hermes-agent`
- Desktop source: `...\apps\desktop`
- Electron user data: `%APPDATA%\Hermes`
- dashboard backend: `python.exe -m hermes_cli.main dashboard ...`
- session workers: `python.exe -m tui_gateway.slash_worker --session-key ...`

The terminal is Windows Git Bash/MSYS, not PowerShell. A Windows venv isolates dependencies; it is not a security sandbox.

Before filing against an old standalone Desktop repository, verify the installed runtime path and git remote. Current integrated Desktop bugs normally belong to `NousResearch/hermes-agent`.

## Core diagnosis

1. Read `hermes config path`, version, and live effective config.
2. Inspect Electron, dashboard backend, worker, and child process command lines.
3. Find the backend port/status endpoint when session ownership matters.
4. Inspect relevant logs at the failing timestamp.
5. Separate:
   - renderer/localStorage state;
   - dashboard/backend state;
   - per-session worker state;
   - `state.db` persisted session metadata;
   - external WSL service state.
6. Reproduce through the actual Desktop path when practical.
7. Prefer supported config/CLI/plugin behavior. If source is defective, use `github-pr-workflow` and a clean worktree rather than leaving the installed tree patched.

## Safety around active Desktop work

Do not run `hermes update`, dependency installs, Desktop rebuilds, broad process kills, or live-source resets while agents/workers are active unless the user explicitly accepts interruption.

For source verification when the live repo is locked or has incomplete dependencies, use a clean temporary worktree/clone, apply only the candidate diff, run targeted checks/build there, and remove generated artifacts afterward.

## Symptom router

### Migration and canonical state

Use when Desktop opens a fresh provider wizard or must inherit a previous CLI/WSL home:

- `references/windows-wsl-desktop-migration-2026-06.md`

Prefer a one-time migration into the Windows home over live cross-boundary SQLite access. Exclude WAL/SHM, locks, caches, and process tracking. Handle locked DBs with staged swap/targeted restore, then verify hashes/counts and Hermes-visible sessions/config.

### Restart, stale workers, ghost sessions

- `references/windows-desktop-renderer-restart-and-scroll-2026-06.md`
- `references/pinned-deleted-session-ghost-rows-2026-06.md`
- `references/windows-desktop-stuck-busy-provider-resume-2026-06.md`
- `references/windows-desktop-agent-session-flood-cleanup.md`

Electron single-instance behavior can focus an existing main process instead of restarting. Confirm the real process tree. For a deleted session still visible, verify DB rows, kill only workers for that session, then clear/reload renderer state; do not wipe all Electron user data. For pins lost during a localStorage-to-SQLite migration, inspect surviving raw LevelDB history with `scripts/recover_chromium_localstorage_key.py` before accepting manual reconstruction; validate recovered IDs against `state.db` and restore only valid lineages. For a source-tagged flood, preserve every matching live runner/child, wait for the top-level runner to exit, then transactionally delete only that exact source; `ended_at IS NULL` is not a reliable liveness signal.

### Project switching and background-status visibility

Use `references/windows-desktop-project-and-background-status-visibility.md` when a chat appears to move, stop, or lose workers after a Project switch or after transient task/subagent UI collapses. Separate workspace/sidebar association, native subagent projection, durable workflow state, task-board reconciliation, and repository diffs before changing or deleting anything.

### Resume, provider drift, and attachment timeouts

- `references/windows-desktop-resume-image-attach-timeouts-2026-06.md`
- `references/windows-desktop-model-route-and-fnm-browser-2026-07.md`

Compare configured model/provider, renderer-persisted composer provenance, session metadata, and backend logs. A fresh-session route can differ from existing sessions. Do not solve provider-state bugs by increasing frontend RPC timeouts.

### Long-task WebSocket disconnects

- `references/windows-desktop-gateway-ws-long-task-disconnect-2026-06.md`
- `references/windows-desktop-gateway-ws-stalls-2026-06.md`

Distinguish the local Desktop/TUI JSON-RPC WebSocket from the messaging gateway. Correlate slow writes, socket resets, detached sessions, and long foreground children. Use tracked background jobs as mitigation; source fixes should address send serialization/backpressure/reattachment, not random timeout inflation.

### Browser CLI discovery

Use `references/windows-desktop-model-route-and-fnm-browser-2026-07.md` when a CLI works in an activated terminal but not Explorer-launched Desktop. Separate CLI discovery from browser availability. Version managers can expose ephemeral shell PATH entries; Desktop should discover stable installation roots and validate the executable.

### Composer, shortcuts, and scroll state

- `references/windows-desktop-composer-shortcuts-2026-06.md`
- `references/desktop-composer-shortcut-source-upstream-2026-06.md`
- `references/windows-desktop-composer-source-patch-verification-2026-06.md`
- `references/windows-desktop-renderer-restart-and-scroll-2026-06.md`

For `contentEditable` shortcuts, compare live DOM text with lagging framework state. Manual DOM rewrites can break native undo. Keep scroll-state loss separate from crashes that merely trigger reload.

### Update counts, generated files, and local diffs

Use `references/windows-desktop-update-shallow-count-and-generated-main-2026-06.md`. Distinguish shallow/no-merge-base update-count errors from a dirty generated Electron bundle and updater autostashes. Verify actual commits and source diff before resetting anything.

### Provider/network stalls

Load `references/hermes-provider-stall-triage.md`. Separate raw DNS/TCP/TLS, Windows-native reachability, Hermes provider/concurrency logs, and auxiliary quota failures before changing networking.

## Verification by layer

- **Renderer fix:** targeted UI test/typecheck/build plus real Desktop reproduction when feasible.
- **Backend/session fix:** status endpoint, exact worker/session key, `state.db` rows, and resume/new-session behavior.
- **Process cleanup:** read process tree after kill; verify current workers remain when intended.
- **Migration:** source/destination hashes or counts, DB integrity, Hermes-visible sessions/config/auth presence without printing secrets.
- **Browser discovery:** doctor plus a real open/title/close cycle from the Desktop-equivalent environment.
- **Source PR:** regression test, targeted/nearby checks, live PR readback, then restore the installed tree clean.

## Pitfalls

- A fresh provider wizard usually means a different `HERMES_HOME`, not deleted state.
- Closing one window does not prove the Electron main/backend exited.
- A healthy dashboard does not prove every session worker is healthy.
- Stale UI after DB deletion does not prove the DB delete failed.
- Do not convert one dated incident into a universal mechanism; re-check current source/logs.
- Preserve detailed dated references as evidence patterns, not automatically current product facts.
