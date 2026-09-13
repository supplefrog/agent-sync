---
name: event-driven-integration-review
description: Review event-driven plugins for lifecycle safety.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [code-review, plugins, lifecycle, idempotency, concurrency, security]
    related_skills: [code-change-verification, repository-inspection-audits, systematic-debugging]
---

# Event-Driven Integration Review

Use this skill for plugins, hooks, webhooks, event consumers, recovery jobs, lifecycle observers, and orchestration adapters whose correctness depends on a host runtime rather than on the changed file alone.

## When to Use

Use when a review involves lifecycle hooks, event-triggered work, delegated or worker isolation, retry/recovery behavior, idempotency, cross-record mutation authority, or claims about zero idle tokens.

## Review contract

Determine whether the integration is safe to ship for:

- lifecycle authority and ordering;
- worker, parent, delegated-child, and operator isolation;
- recursion prevention and bounded work;
- at-most-once or exactly-once claims;
- persistence and retry behavior;
- prompt-injection, provenance, and trust-boundary risks;
- zero-idle-token or no-standing-agent requirements.

Return only evidence-backed blocking findings or a ship verdict. For each blocker give the exact file/line, concrete impact, reproduction or traced host path, and smallest complete fix.

## Workflow

1. **Inventory the contract and seams.** Read the implementation, manifest/config, recovery path, focused tests, and docs. Identify the event producer, callback process, persistence write, retry/recovery path, and any user/operator handoff.
2. **Trace the host runtime.** Inspect the real host source for hook names, callback kwargs, firing process, commit ordering, exception handling, child identity, and mutation guards. Do not infer runtime behavior from the plugin’s comments or mocks.
3. **Check identity in the host’s actual mechanism.** If the host uses ContextVars, task-local state, session metadata, or scoped runtime state, test those directly. An environment-variable check is insufficient when delegated work runs in-process and inherits the parent environment.
4. **Challenge exclusion and recursion boundaries.** Exercise normal parent/operator, worker, delegated child, recovery-script, and nested-event paths. Verify that caretaker/consumer-generated events are excluded by trusted provenance rather than only by spoofable titles or strings.
5. **Prove idempotency at the persistence boundary.** Locate the uniqueness constraint or atomic insert-or-return operation. A read-side existence check followed by a later insert is not at-most-once. Force concurrent callers past the pre-check and run the real DB/API path; inspect resulting rows and returned IDs.
6. **Validate lifecycle authority.** Ensure observers run after durable commit when required, and that the integration never applies cross-card state changes outside the host’s guards or judges. Structured handoffs must be tied to authenticated/provenanced producer records and current event identity.
7. **Validate token behavior.** Confirm that recovery is script-only when promised, that no idle polling agent is launched, and that user-turn context injection is bounded to one current item and excluded from worker/child sessions.
8. **Separate deployment layout from source layout.** If a script resolves sibling installed directories, test it in the documented installed layout before calling a source-checkout invocation a production defect. Record source-only failures separately.
9. **Run verification.** Execute focused tests, syntax checks, and at least one real runtime probe for each high-risk boundary. Report passing checks alongside blockers; do not let green mocks overrule a failing production-path reproduction.

## Evidence standards

Prefer, in order:

1. a real host source trace with exact lines;
2. a deterministic runtime probe against a temporary profile/database;
3. a focused regression test driving the production seam;
4. static reasoning tied to an explicit schema/transaction invariant.

For concurrency probes, synchronize callers after the idempotency lookup and before the write transaction. For isolation probes, invoke the callback inside the host’s real child context with inherited environment unchanged. Record both returned values and durable state.

## Common blocking patterns

- **ContextVar/env mismatch:** in-process children use a ContextVar, but the integration checks only an env marker.
- **Check-then-create race:** idempotency is claimed, but the key has only a non-unique index or no atomic conflict handling.
- **Untrusted handoff:** any comment/event carrying a recognizable marker can wake an operator or parent without producer provenance.
- **Observer authority leak:** a callback performs mutations directly or bypasses the host’s cross-card ownership/judge guard.
- **Retry amplification:** recovery and native hooks use different keys, event cursors, or archived-row semantics, producing duplicate work.
- **Idle-token violation:** a periodic agent or repeated unresolved context injection is used where a script-only repair or one-shot handoff was required.

## Pitfalls

- Focused tests often prove only sequential behavior; add a forced race and a real subprocess/in-process context probe.
- “The callback is best-effort” does not make dropped lifecycle work correct; verify the recovery path repairs it.
- A marker’s current event ID does not establish who authored it; verify producer provenance separately.
- A non-unique database index accelerates lookup but does not enforce idempotency.
- Do not report a source-tree path mismatch as a production blocker when deployment explicitly relocates the script; do verify the documented layout.

## Reference recipe

See `references/host-runtime-probes.md` for deterministic probes and evidence patterns for ContextVar isolation, concurrent idempotency, and untrusted handoff validation.
