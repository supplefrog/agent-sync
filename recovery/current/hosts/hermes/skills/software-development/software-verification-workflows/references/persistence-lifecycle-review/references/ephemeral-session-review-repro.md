# Ephemeral-session review reproducers

Use a temporary real SQLite database and the production `SessionDB` methods. Keep owner PID/start values fixed in the fixture so each result isolates the lifecycle guard.

## Failure-state deletion probe

Create parent + child, register ownership, end the child, mark terminal state `error`, then call `acknowledge_ephemeral_session_output()` with the exact owner PID/start. Expected: `False`; child and ownership row remain. Any `True`/missing child means the deletion predicate treats failure as success.

Also exercise `timeout`, `interrupted`, `unknown`, and crash-recovery-protected rows. A `finally` path that substitutes a truthy fallback such as `unknown` is still unsafe if acknowledgement only checks non-null state.

## Foreign-key deletion probe

With foreign keys enabled, register an ownership row and call the normal parent/session deletion API. Expected: ordinary deletion succeeds and leaves no ownership rows. An `IntegrityError` indicates the new ledger references are not integrated with existing delete paths. Check single delete, bulk delete, prune, empty-session cleanup, and delegate-child cascade.

## Lazy-registration ordering probe

Do not use a mocked registration helper for this check. Construct the real child object with the shared `SessionDB`, but do not invoke its first-turn/session-creation method; call the production ownership-registration adapter and inspect the result. If the adapter returns no handle and the ownership table remains empty, registration is occurring before the lazy child row exists. The complete fix is to create/ensure the child row immediately before registration, then verify the handle is serialized for async dispatch and terminal acknowledgement.

For a public lifecycle service, trace the construction-to-registration seam separately from the lower-level adapter. A real reproduction with a parent row, a child object sharing the DB, and no child row should leave `ephemeral_handle=None` and zero ownership rows when launch skips the child’s lazy `_ensure_db_session()`. After the fix, assert a non-null handle, one ownership row, terminal marking, and successful `acknowledge_output()` cleanup. Existing tests with fake children lacking `_session_db` do not cover this ordering bug.

## Generic-prune bypass probe

After registering and terminally marking a child, make its session/message timestamps stale and invoke the real `prune_sessions()` path without acknowledging output. Expected: the child remains; generic pruning must exclude unintegrated ephemeral ownership rows. A result such as `pruned=1` with `child_after_prune=None` proves the maintenance path bypasses lifecycle authority.

## Filtered-export race probe

Force an acknowledgement between `export_all()` candidate selection and its protection call. If the export returns the selected session with stale metadata but zero messages, selection and protection are split across transactions. Fix by selecting and protecting the export set atomically before reading payloads.

## Delivery-cleanup partial-failure probe

Force `_acknowledge_ephemeral_children()` to fail after `complete_completion_delivery()` updates the durable delivery row. If the row is already `delivery_state='delivered'`, cleanup has no retry authority and the child can be stranded. Add a durable cleanup-pending/retry state or another independently replayable cleanup mechanism.

## Path coverage checklist

- synchronous child: registration, terminal mark, parent durable output flush, acknowledgement;
- asynchronous child: serialized opaque handle, delivery claim/ack, child cleanup;
- restart: dead PID or mismatched process-start is retained/protected, never deleted;
- external process: child session creation is followed by ownership registration, not just `parent_session_id` metadata;
- user interaction: title/archive/pin/export/resume/adoption/protection blocks cleanup;
- post-terminal append/edit/lease/descendant blocks cleanup.

## Evidence format

Record the exact command/test, returned boolean, exception, and final rows for parent, child, messages, ownership, leases, and delivery state. Report the smallest complete fix, including migrations when a schema change affects already-created tables.
