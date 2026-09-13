---
name: persistence-lifecycle-review
description: Use when reviewing durable-state cleanup changes.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [persistence, lifecycle, retention, cleanup, crash-recovery, code-review]
    related_skills: [code-change-verification, systematic-debugging, github-code-review]
---

# Persistence and Lifecycle Review

## When to Use

Use when reviewing changes that create, retain, adopt, integrate, recover, or delete durable state, especially ownership ledgers, ephemeral records, cleanup jobs, restart recovery, or session deletion.

The goal is to prove both safety (nothing is deleted on failure or ambiguity) and liveness (successful temporary state eventually cleans up) at the real production seams.

## 1. Define the lifecycle contract

Write the state machine before judging the patch:

- creation and ownership receipt;
- active/inactive and terminal transitions;
- durable output integration or acknowledgement;
- adoption/protection/reference/lease rules;
- successful deletion;
- failure, timeout, ambiguity, crash, and restart behavior.

Separate **deletion authority** from **evidence that work stopped**. A dead process, source tag, non-null terminal marker, or matching title is not by itself authority to delete durable content.

## 2. Inventory every path

Trace every producer and consumer, not just the changed function:

- synchronous and asynchronous execution;
- batch and single-item execution;
- restart recovery and replay;
- external/process-spawn adapters;
- lazy session/resource creation before ownership registration (construction may not create the durable row);
- user resume, title, archive, pin, export, and delete operations;
- single, bulk, prune, empty-state, and parent-cascade deletion APIs.

For each path, record where the ownership token is created, where terminal state is recorded, and where durable output integration triggers cleanup. If a handle is registered on one path but acknowledged only on another, the lifecycle is incomplete.

## 3. Review ownership and trust boundaries

Opaque ownership receipts should bind the exact parent, child, owner kind, PID, and process-start identity. Validate both PID and start identity at acknowledgement and recovery so PID reuse cannot confer authority. Verify that process-spawn adapters actually register after the child session row exists; metadata-only parent linkage is not ownership.

Keep public/user-facing identifiers separate from deletion capabilities. Do not rediscover sessions by source, title, timestamp, or broad parent queries when an exact receipt is available.

## 4. Review terminal-state guards

Treat terminal-state values as a correctness boundary. Deletion should use an explicit success allowlist—normally exactly `completed`—rather than merely testing that a terminal marker is non-null. Exercise:

- success;
- timeout;
- exception/error;
- cancellation/interruption;
- unknown or crash-recovered outcome;
- post-terminal message/content mutation.

Early-return and `finally` paths are high-risk: confirm the status variable is initialized and populated before cleanup bookkeeping runs. Failures and ambiguity must retain or protect evidence.

## 5. Review transaction boundaries and partial failure

Audit generic cleanup APIs separately from the new ownership-aware path. Include specialized maintenance selectors such as never-active keyed-session cleanup, routing-index repair, and any helper that first materializes candidates before calling a broader delete API. A successful lifecycle acknowledgement must not be bypassed by bulk prune, empty-session cleanup, parent-cascade, or user-facing delete helpers unless the contract explicitly grants that authority. For any selector-driven deletion, verify the guard is in the selector that feeds the destructive caller—not only in a preview/list API—and cover the authority boundary in both directions: an owned stale parent and owned child survive, while an otherwise equivalent unowned stale candidate is still pruned.

For each destructive operation, identify the transaction containing:

1. the final eligibility read;
2. the ownership/lease/reference checks;
3. the integration marker update;
4. message/session/ledger deletion.

The eligibility check and destructive mutation must be atomic. Durable output integration must precede child deletion. Post-commit filesystem cleanup should be best-effort and must not falsely report durable deletion. If acknowledgement fails after delivery, determine whether retry remains possible; otherwise retention is safer than silent loss.

## 6. Audit foreign keys, deletion APIs, and migrations

Inspect every new foreign key and the database's actual `PRAGMA foreign_keys` setting. Then trace all existing delete mechanisms. New ownership rows must not make ordinary parent/user deletion raise an integrity error or leave ledger rows behind.

For additive durable state, audit both the fresh schema and every legacy migration/rebuild path. A column added by an additive migration can still be lost later when a drift-repair table rebuild recreates the table from a stale canonical spec. Verify rebuilt tables retain new columns and that shared-column copy logic preserves old values (or safely defaults missing legacy columns). Exercise at least one real legacy-shaped database through the full open/migrate/reload path, then inspect `PRAGMA table_info` and perform the first write that depends on the new column.

For leases and ownership rows, do not let a generic expired-row purge become a second authority path. An expired lease may still belong to a task/run that is being extended or whose worker is alive; release it only in an atomic reclaim/end-run transition or after rechecking the owning run's durable state. Also audit defensive recovery branches that close stale runs directly rather than calling the normal end helper: they must release every run-scoped lease before the next claim attempts to insert a replacement.

When a worker can outlive reclaim or handoff, every side-effecting retry/failure callback must carry the originating run/attempt ID and compare it under the same write transaction before incrementing counters, ending a run, releasing a lease, or changing task status. A prior status check is not sufficient: an operator or dispatcher can reclaim the old run and claim a successor between that check and the callback. Exercise the interleaving explicitly: old run observes `running`, successor claims, old callback fires, and successor state must remain unchanged. Apply the same CAS rule to quiet operational retry paths, transient-block handlers, timeout callbacks, and review-worker handoffs; ordinary terminal tools that already accept `expected_run_id` are the reference pattern.

For subprocess/session isolation, enumerate the complete authoritative context/environment registry rather than maintaining a partial hand-written scrub list. Scrub all inherited parent/controller routing values, but preserve only the delegated child's own local identity when crossing a process boundary (for example its child session ID/source/platform). Verify both properties independently: parent UI/chat/profile/cron delivery values must not survive, and the child session ID must still be available to child subprocesses for persistence and attribution.

Use one of these complete designs:

- `ON DELETE CASCADE` for ownership references, with a real migration/rebuild for already-created tables; or
- explicit ledger deletion inside every session-deletion transaction, including child cascade, bulk, prune, empty-session, and parent deletion paths.

Do not assume deleting messages or orphaning `parent_session_id` removes ownership rows.

## 7. Verify with small real reproducers

Run targeted tests, then add tiny production-database probes for each destructive boundary:

### Required hidden-path checks for ephemeral/delegated state

- Trace construction-to-registration ordering through the real lazy-row creation seam. A helper that requires an existing child row must be preceded by an explicit ensure/create operation; a unit test that pre-creates the row does not prove the production path.
- Compare the identity actually persisted by the producer with the identity accepted by the cleanup authority. In-process ContextVars and inherited environment values can produce a source/owner mismatch even when subprocess scrubbing tests pass. Probe both an unbound environment and a parent-bound controller context.
- Exercise every generic deletion surface—single, bulk, empty-session, prune, parent cascade, and maintenance cleanup—against an owned but not-yet-integrated child. Foreign-key cascade success is not lifecycle-authority success: unintegrated ephemeral rows must not disappear through a generic path.
- Audit helper predicates and preview/count APIs for parity with the destructive operation. `list_*_candidates`, count endpoints, and empty-session checks must not advertise owned rows as deletable when the final delete path retains them; conversely, an automatic empty-session helper such as `delete_session_if_empty` is still a generic cleanup path and needs the same ownership guard unless it explicitly carries the owner receipt.
- Exercise lazy construction with a real agent constructor and temporary DB, not only a mock builder: verify source/parent marker persistence, ownership minting after row creation, child-only ContextVar/environment identity inside the scope, and restoration of the parent identity afterward.
- Exercise legacy backfills that synthesize active-run rows, not only table rebuilds. New immutable per-run fields must be populated for migrated in-flight work or explicitly marked unknown/protected.

See `references/human-off-orchestration-probes.md` for reusable probes and evidence patterns.

- successful terminal child is deleted only after acknowledgement;
- error/unknown child survives acknowledgement;
- a parent/user session with an ownership row can still be deleted;
- descendant, lease, adoption, protection, and post-terminal writes block deletion;
- sync, async, restart, and process-spawn paths all register and eventually acknowledge;
- PID reuse or mismatched process start fails closed.

Prefer exact observed exceptions, row state, and deletion results over inferred safety. A happy-path test that duplicates the proposed algorithm is not sufficient.

## Completeness and race-audit addendum

For orchestration patches that add a lifecycle state or handoff, verify the feature is actually reachable end to end, not merely represented in prompts or state-machine branches. Search the real tool registry/schema and every CLI/API surface: a prompt naming a tool is not evidence that the tool exists, and a branch recognizing a status is not evidence that any producer can emit it. Check status enums, list/show receipts, dispatcher selectors, reviewer return paths, and notification events together.

Make the originating run/attempt ID mandatory in every side-effecting callback. Audit existing timeout, crash, iteration-budget, stale-worker, retry, and handoff callers—not only the newly added path. A CAS helper with an optional expected ID does not protect callers that omit it; exercise the interleaving where the old run is reclaimed, a successor claims, and the delayed callback fires.

For destructive maintenance, keep candidate selection, the final eligibility/ownership/reference read, and deletion in one write transaction. A list-then-delete implementation can delete a row that becomes active between those calls. Treat routing/index rows and JSON-encoded references as durable state: remove exact references inside the same transaction as the acknowledged deletion, or retain the target. Test the actual selector-to-destructive-caller path, not only preview/count APIs.

When isolation is ContextVar-based, audit raw ``os.environ`` reads separately. ContextVar masking does not stop code that reads inherited process-global environment values directly; every such read must use a context-aware accessor or an explicit ownership predicate.

See ``references/orchestration-lifecycle-review-probes.md`` for compact reproducer patterns covering feature reachability, stale successor-run callbacks, non-atomic pruning, and durable routing references.

## Output

For each blocking finding, report:

- path and line;
- concrete impact;
- traced input/state/interleaving or real repro output;
- smallest complete fix.

End with one verdict: **ship**, **fix then ship**, **rework**, or **reject**. If clean, state the paths tested and the important untested scope.

## Pitfalls

- Non-null terminal state is not equivalent to successful completion.
- A new foreign key can silently break unrelated user deletion APIs.
- Async-only acknowledgement does not prove synchronous cleanup.
- Parent linkage without an ownership receipt does not support crash recovery.
- Marking delivery complete before cleanup can strand retained children; safety is preserved, but liveness and retry behavior must be explicit.
- Do not report speculative lifecycle concerns without tracing callers and running a minimal repro.

See `references/ephemeral-session-review-repro.md` for concrete probes and evidence patterns from a representative review. See `references/legacy-rebuild-and-lease-probes.md` for migration-rebuild and run-lease reproducer patterns. See `references/never-active-prune-authority.md` for a focused owned-parent/owned-child retention and legitimate-unowned-pruning probe.
