# Human-off orchestration lifecycle probes

Use temporary databases and isolated subprocess/context probes. Do not rely on pre-created fixtures alone.

## 1. Lazy registration ordering

Trace the real producer from child construction to first-turn/session-row creation. If registration queries `sessions` by child ID, construct the child without running its first turn and invoke the production registration adapter. Expected: the adapter explicitly ensures the row, persists exact lineage, and returns one opaque receipt. A `None` receipt with zero ownership rows means cleanup liveness is missing.

## 2. Producer identity versus authority identity

Probe both contexts:

- no bound parent session environment/context;
- a parent-bound controller context with source, session key, chat, user, and async-delivery values.

Call the same source/owner derivation used by child creation, then compare it with the exact identity allowlist used by registration/acknowledgement. Subprocess env scrubbing is insufficient: in-process ContextVars can preserve parent authority while the child runs.

Expected: child execution has its own authenticated identity and cannot inherit controller routing/session authority. A source mismatch between the real producer (`subagent`, inherited `kanban`, etc.) and a hard-coded registration requirement proves registration will fail in production.

## 3. Generic cleanup bypass

Create parent + owned child in a temporary real `SessionDB`, leave ownership active or terminal-but-unintegrated, mark the child ended, then run each real cleanup surface:

- `delete_empty_sessions()`;
- `prune_sessions()` with an explicit broad age bound;
- bulk deletion;
- parent cascade.

Expected: generic maintenance paths retain unintegrated children. A user-explicit parent delete may be allowed only if the contract grants that authority; record it separately from caretaker/prune behavior. If the child disappears and the ownership row cascades away without an integration acknowledgement, deletion authority is bypassed.

## 4. Legacy active-run receipt backfill

Build a legacy-shaped board with a running task whose task-level route fields are populated but whose synthesized `task_runs` row lacks the new receipt column/value. Run the public migration/open path, inspect the active run, and verify the receipt is populated from the route snapshot (or explicitly marked unknown/protected). A table-rebuild test alone does not cover this data backfill.

## 5. Lease release audit

Enumerate every path that clears `current_run_id` or changes a running task to another status. Confirm each path deletes the exact `(task_id, run_id)` lease in the same transaction. Include defensive stale-run recovery, review reopen, unblock, archive, hard delete, and failure/circuit-breaker transitions. A later claim that opportunistically removes an orphan is repair, not proof that the original lifecycle path was atomic.

## 6. Stale-worker successor race

Use a real board DB to claim run A, reclaim it, claim successor run B, then invoke the old worker's timeout/transient/failure callback with the task ID. Expected: run B remains running, its lease remains present, and its failure counter/status are unchanged. A callback that re-reads the task's current run without an `expected_run_id` CAS can close B, release its workspace lease, or trip the circuit breaker. A status check performed before the callback is not enough because reclaim/claim can interleave between the check and the write transaction.

## 7. Complete context scrub with child identity preservation

Build an environment containing every authoritative session/controller key: durable session ID/key, UI session ID, profile, source/platform, chat/thread/user/message IDs, async-delivery flag, cron marker, and cron auto-delivery target fields. Run the production subprocess-env builder inside a delegated child context and also with only the delegated-process marker.

Expected in both cases: parent controller/UI/chat/profile/cron routing values are absent. Inside the real child context, the child’s own session ID (and explicitly child-local source/platform if required by the subprocess contract) remains available. With only an inherited marker and no child ContextVar identity, no foreign session ID is synthesized. This catches both partial scrub lists and over-scrubbing that breaks child attribution.

## Evidence standard

Report exact path/line, observed return values, final rows, and the smallest complete fix. Separate safety (no premature deletion/double writer) from liveness (successful work eventually cleans up); a green happy-path test does not establish either for generic cleanup or lazy construction paths.
