# Safe cleanup of agent-created session floods

Use when one live Desktop session launches many one-shot Hermes sessions (for example eval runners with a dedicated `--source` tag), crowding the sidebar or hiding pinned/history rows.

## Safety invariant

A session row being untitled, old, `ended_at IS NULL`, or absent from the DB does **not** prove its process is idle. One-shot Hermes sessions can leave `ended_at` null after completion, while a DB-less worker can still be running. Never kill or delete based on those fields alone.

## Workflow

1. Identify the exact generated-session source tag from recent rows and process command lines. Do not classify ordinary `desktop`, `subagent`, `tool`, or pinned sessions as flood rows.
2. Inspect live process command lines for both the runner and children, including:
   - the runner script (for example `tools/eval.py`);
   - `hermes ... --source <tag>` children;
   - `tui_gateway.slash_worker` processes.
3. If a matching runner or child is live, preserve it. Monitor the top-level runner PID until it exits, then inspect again. Do not stop, pause, or delete its rows merely to clear the sidebar.
4. Only when no process matches the source tag or runner, transactionally delete rows for that exact source from:
   - every table carrying `session_id` (currently including `messages` and `session_model_usage`);
   - `sessions` last.
5. Preserve all other sources and renderer localStorage. Pinned state belongs to Electron localStorage, not `state.db` session metadata.
6. Verify:
   - zero rows remain for the exact source;
   - current and important Desktop session IDs still exist;
   - `PRAGMA integrity_check` returns `ok`;
   - no matching runner/child process is live.
7. Let the Desktop sidebar refresh naturally. Reload only if stale rows remain; do not broadly clear `%APPDATA%\Hermes`.

## Resume-crash repair for async delegation metadata

If opening an important session fails with an error like `Cannot use 'in' operator to search for 'task_count' in '{...}'`, inspect the exact message. If its content is intact and only `display_kind='async_delegation_complete'` / string `display_metadata` triggers the renderer crash, set those two display fields to `NULL` for that one message. This preserves the full message as ordinary text. Verify the content length and session message count afterward.

## Pitfalls

- Deleting while the runner is live causes it to create more rows and can interrupt real work.
- Killing broad Python/Hermes process trees can terminate unrelated active sessions.
- `ended_at IS NULL` is not a live-process signal for one-shot sessions.
- Source-specific eval rows are independent sessions, not a compression lineage; do not use compression-tree deletion unless they actually share a parent tree.
