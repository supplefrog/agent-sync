---
name: hermes-compression-tree-delete
description: Delete an entire Hermes context-compression session tree when the user gives a session id, session title/name, or says old compressed sessions keep reappearing. Use this instead of deleting one visible session. It deliberately deletes, not archives, and does not create backups unless the user explicitly asks.
---

# Hermes compression tree delete

## Fast path

The user has already authorized deletion by asking for it. Do not add a confirmation round, preliminary DB inspection, achievement scan, or manual process hunt.

Run the bundled script in **one terminal call**, using the absolute `skill_dir` returned by `skill_view`:

```bash
python "<skill_dir>/scripts/delete_tree.py" "<session-id-or-exact-title>"
```

The script performs the whole workflow atomically enough for this use case:

1. Resolves the active Hermes home with `get_hermes_home()`.
2. Matches an exact session id first; otherwise matches the exact title and numbered continuations.
3. Walks to the oldest ancestor and collects the full descendant compression tree.
4. Refuses title matches spanning unrelated roots.
5. Deletes `compression_locks`, messages, and sessions directly in one SQLite transaction.
6. Verifies no collected session or message rows remain.
7. On Windows, kills only stale `python.exe -m tui_gateway.slash_worker` processes whose command line contains a deleted id.
8. Prints one JSON result with deleted ids/counts, worker PIDs, and `verified: true`.

Report the result briefly. If the script exits nonzero, report its exact error; do not fall back to a long manual workflow unless the error identifies a real compatibility problem.

## Options

Use only when needed:

```bash
# Inspect without deleting
python "<skill_dir>/scripts/delete_tree.py" "<query>" --dry-run

# Delete DB rows but intentionally leave workers alone
python "<skill_dir>/scripts/delete_tree.py" "<query>" --keep-workers
```

Do not use `--dry-run` before a normal exact-id deletion; it doubles the work without changing the decision.

## Important behavior

- Delete the complete compression lineage/tree, not just the visible tip.
- Do not use `hermes sessions delete <id> --yes` from Desktop/TUI. It has previously deleted a different session than the positional id while reporting success.
- Do not archive and do not create a backup unless explicitly requested.
- Do not refresh or delete achievement state during routine deletion. Preserve `plugins/hermes-achievements/state.json`, `scan_snapshot.json`, and `scan_checkpoint.json`. There is no need to search for a rescan command before deletion.
- Do not delete by a `#N` title suffix alone. If title matching spans unrelated roots, the script stops and asks for an exact id.
- If a deleted row remains visible after the script reports verification, reload Desktop. Only then inspect renderer/sidebar caching; the stale worker case is already handled by the script. See `references/deleted-pinned-session-visible-in-desktop-2026-06.md`.

## Why the bundled script exists

The previous multi-command workflow was slow and error-prone: it repeated config discovery, assumed optional schema columns such as `updated_at`, searched for an achievement rescan path that was not needed, and used broad process queries that matched their own PowerShell command line. Keep this operation on the deterministic one-call path.
