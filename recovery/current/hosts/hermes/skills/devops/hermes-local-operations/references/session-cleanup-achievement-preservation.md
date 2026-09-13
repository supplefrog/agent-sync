# Session cleanup and Hermes achievements preservation

Use when deleting old Hermes sessions/compression trees while the `hermes-achievements` plugin is installed.

## File roles

- `plugins/hermes-achievements/state.json`: persistent achievement state. Historically stored unlocks; after the monotonic-progress fix, should also persist lifetime aggregate/progress counters.
- `plugins/hermes-achievements/scan_snapshot.json`: last computed dashboard payload/progress. Useful as the current visible dashboard state, but can be overwritten by future rescans.
- `plugins/hermes-achievements/scan_checkpoint.json`: speed cache for rescans. Not the source of achievement truth.
- `state.db`: session rows/messages. Deleting sessions removes source evidence for future scans.

## Safe workflow before deleting sessions

1. Refresh achievements first: open Achievements dashboard and wait for scan completion, or call the plugin rescan endpoint if operating the dashboard API directly.
2. Keep `state.json` and `scan_snapshot.json` unless the user explicitly wants a fresh recompute or stale dashboard/search references removed.
3. Delete session/compression tree rows/messages from `state.db` only after achievement refresh.
4. Do not force an achievements rescan after deletion unless the user accepts progress being recomputed from the smaller session DB.

## Durable fix direction

Achievement lifetime progress should be monotonic and persisted in `state.json`, not only recomputed from prunable session rows. The fix pattern is:

```python
persisted = state.setdefault("lifetime_aggregate", {})
merged[key] = max(persisted_value, scanned_value)
```

Then future scans over a pruned/deleted session DB cannot lower already-earned lifetime progress.

## Communication rule for this user

Answer this topic crisply:

- `state.json` = earned/unlocked + persisted lifetime progress.
- `scan_snapshot.json` = current dashboard view/progress snapshot.
- `scan_checkpoint.json` = rescan speed cache.
- Deleting sessions affects future recompute unless lifetime progress is persisted.
