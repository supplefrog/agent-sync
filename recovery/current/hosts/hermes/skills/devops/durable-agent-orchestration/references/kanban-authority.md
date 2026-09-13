# Kanban authority and reconciliation

## Authority

- Dispatcher workers mutate only their own scoped lifecycle.
- Delegated children do not mutate Kanban.
- Caretakers gather source evidence but do not mutate source cards.
- Trusted supervisors apply foreign-card actions only through supported APIs with board, source task, current event, evidence, idempotency, CAS, and readback bound together.

## Routing

Route review-required work to native review, genuine input/capability boundaries to blocked, transient faults to bounded retry, repeated same-cause blockers to triage, and terminal completion to a supervisor-only evidence gate. Treat a crash or gave-up event as recovery evidence, not acceptance evidence.

Interrupt only for human review, one exact ambiguity, or a required input/capability decision. Keep completion, unblock, keep-blocked, retry, recovery, and audit results as quiet durable receipts.

## Tests

Test native review routing, one-shot decision alerts, quiet receipts, stale/forged/contradictory evidence rejection, changed-event invalidation, concurrent idempotency, worker/child ownership guards, installed-source parity, and denial of terminal review after a crash without acceptance evidence.
