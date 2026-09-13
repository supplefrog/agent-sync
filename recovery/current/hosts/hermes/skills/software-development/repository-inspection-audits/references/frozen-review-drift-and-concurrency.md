# Frozen-review drift and concurrency probes

Use this reference when independently verifying a stateful pilot or immutable release artifact.

## Freeze and identity

1. Before execution, record the exact source-tree hashes, untracked-file state, receipt hashes, image tag resolution, and immutable image digest.
2. Run the required command against that digest or verify the tag still resolves to the recorded digest immediately before starting.
3. Re-check source, receipts, tag, and digest after execution. If another process changed them, do not combine the before/after results or silently rerun the replacement. Preserve the original output and report the requested frozen artifact as unavailable or uncertifiable when its digest disappeared.
4. A receipt that records a digest after execution does not pin the artifact by itself.

## Concurrency

Sequential retry/idempotency tests are insufficient for durable conversation state. Exercise overlapping calls through the real runtime seam:

- distinct turns/commands, to expose lost whole-state writes;
- same-turn retries, corrections, and approvals, to expose duplicate or conflicting durable events;
- repeated natural-concurrency trials plus one deterministic overlap barrier when timing makes the race hard to reproduce.

A barrier-induced hang may be a probe design issue (for example, synchronizing while a database read lock is held), so diagnose that separately. A repeatable lost task/event or a conflicting final decision is a production blocker. Keep one-process, repeated-ingress, and multi-process/shared-checkpointer claims separate; never promote a unit test to a cross-process guarantee.
