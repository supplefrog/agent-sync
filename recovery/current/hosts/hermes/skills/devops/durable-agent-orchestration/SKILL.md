---
name: durable-agent-orchestration
description: Use for durable agent state, retries, and authority.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [agents, orchestration, persistence, kanban, authority]
    related_skills: [agent-orchestration-operations]
---

# Durable Agent Orchestration

Use this class-level skill for integrity and authority across persisted DAGs, routed workers, retries, cancellation, Kanban reconciliation, and supervisor actions.

## Runtime integrity

- Keep one authoritative lifecycle owner and serialize cross-process read-modify-write transitions.
- Bind normalized plans, route catalogs, selector bytes, and receipts to immutable host-trusted run evidence; validate provider/model/effort/route as an allowed tuple because self-consistent worker receipts are not authority.
- Persist one launch claim, native handle, and unique attempt token before spawn; require the current handle/token for completion because stale workers must not finalize retries.
- Give each physical attempt a unique output path and count interrupted or orphaned work against the original budget.
- Reconcile the exact native process tree before retry; a missing parent or launcher is not proof that descendants ended, and unknown liveness fails closed.

## Kanban authority

- Use native `review` for review handoffs, typed blockers for real dependency/input/capability/transient boundaries, `triage` for unresolved recurrence, and `done` only for evidenced terminal results.
- Keep workers and delegated children scoped to their own task lifecycle; foreign-card actions belong to a board-scoped trusted operator or supervisor.
- Bind supervisor actions to board, source task, current source event, acceptance evidence, idempotency, CAS, and exact readback because free-form recommendations are not mutation authority.
- Interrupt the user only for genuine decisions; keep completion, retry, recovery, audit, and keep-blocked receipts durable but quiet.

## Verification

Exercise duplicate claims, stale completions, coordinated plan/catalog tampering, out-of-catalog receipts, traversal and hardlinks, surviving descendants, malformed handles, concurrent supervisor scans, changed-event invalidation, forged evidence, worker/child ownership guards, and source-versus-installed parity. Read `references/runtime-integrity.md` and `references/kanban-authority.md` for the implementation matrix.
