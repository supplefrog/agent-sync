# Orchestration lifecycle review probes

Use these probes when a patch combines orchestration state, retries, and durable cleanup.

## Feature reachability

1. Search every newly named lifecycle tool/status in the real registry, schemas, CLI/API routes, and dispatcher selectors.
2. Confirm at least one producer can emit the status and one consumer handles it.
3. Verify list/show/status receipts include the new state, and notification/watch paths preserve it.
4. A prompt string or an `if status == ...` branch alone is not implementation evidence.

## Successor-run CAS

Model the interleaving explicitly:

1. Run A is `running` and records `run_id=A`.
2. Reclaim/end A and allow a successor to claim `run_id=B`.
3. Fire A's delayed timeout/crash/retry/budget callback.
4. Assert B remains running, its claim/lease is intact, and its failure counter/status are unchanged.

Every side-effecting callback must carry A's ID and compare it in the same write transaction before changing task status, counters, claims, leases, or run rows. Audit old callers as well as new ones; an optional CAS parameter is ineffective when callers omit it.

## Non-atomic pruning

A selector-based cleanup must not do `list_candidates()` followed by independent deletion. Insert a message/activity marker between selection and deletion (or use two real DB connections) and assert the newly active row survives. The final eligibility read and destructive mutation belong in one transaction.

## Exact durable references

For a successful ephemeral deletion, create an exact reference in every durable routing/index table that can point at the child, then acknowledge integration. Assert the child is retained or the reference is removed atomically. JSON-encoded session IDs are references even when no SQL foreign key exists; do not rely only on child metadata such as `session_key`, title, or handoff fields.

## Context isolation

Enter the delegated-child ContextVar scope while parent routing environment variables remain set. Exercise both a context-aware accessor and a direct `os.environ` read. The former must see child/empty identity; the latter is a leak unless guarded by an explicit dispatcher-owned predicate. Repeat inside a child subprocess and verify the child-local identity survives while parent controller/delivery values do not.
