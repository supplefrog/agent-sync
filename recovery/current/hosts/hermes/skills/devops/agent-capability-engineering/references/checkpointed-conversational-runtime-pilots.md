# Checkpointed conversational runtime pilot patterns

Use this reference after a checkpointed graph/runtime is selected as conversational authority and a thin composer is being piloted. It covers failure modes that ordinary persistence and happy-path fan-out tests miss.

## Authority invariant

The checkpointed conversation state is the only task ledger. Worker runtimes return typed receipts; they do not independently decide canonical task status. Every turn, approval, cancellation, failure, policy promotion, and executor completion must become one attributable state transition.

## Same-conversation mutation safety

A checkpointer preserves versions; it does not necessarily serialize two invocations that read the same thread head. Concurrent turns can both succeed while one branch becomes the visible head and silently hides the other.

For a single-process pilot:

1. Serialize each conversation's read/decide/write checkpoint phase with a per-conversation lock.
2. Mark selected tasks `running` and persist that transition while holding the lock.
3. Release the lock before invoking long-running workers so new turns, status queries, and steering are not blocked.
4. On worker completion or failure, reacquire the lock, reload the latest checkpoint, and merge receipts into current tasks by stable ID. Never write the pre-execution task snapshot back wholesale.
5. Serialize approval, cancellation, rollback, and other same-thread mutations through the same lock.

An in-process lock is not a distributed guarantee. Before multi-process deployment, replace it with the runtime/server's supported thread run queue, optimistic concurrency token, database transaction/advisory lock, or equivalent single-writer mechanism. Prove that mechanism separately.

### Required concurrency probes

- **Simultaneous turns:** release two same-thread submissions from a barrier. Both task identities and both turn IDs must persist, with no error hidden by last-writer-wins behavior.
- **Turn during execution:** block the executor after the `running` checkpoint is durable, submit another turn, then release the worker. The new turn must complete promptly and remain present/pending after old work commits.
- **Completion and error merge:** add state while a worker runs, then exercise both success and exception paths. Neither path may overwrite newer tasks or policy state.
- **Stress:** repeat the simultaneous-turn probe enough times to expose scheduling variance; report lost runs, not only test exit status.
- **No implicit retry:** after an ambiguous batch failure, affected running tasks should become `needs_review` (or an equally explicit state) and must not rerun automatically.

## Governed runtime self-modification

A task named "self-modification" or an artifact describing a change is not proof that the runtime changed.

A bounded pilot should:

1. whitelist a narrow typed policy surface and reject unknown keys or invalid values;
2. require an attributable, idempotent approval decision before execution;
3. record the policy version on which the proposal was staged;
4. apply the promoted policy to a real runtime seam (for example executor concurrency), then observe that the real executor consumed it while still running the real worker path;
5. persist the promoted policy and verify it after a fresh runtime instance;
6. retain previous and promoted policy receipts;
7. permit rollback only when the current policy still equals the promoted version, so rollback cannot overwrite a newer change;
8. make rollback decisions idempotent and preserve promotion/rollback lineage.

Keep code/tool rewriting behind immutable image or revision promotion until isolated held-out evaluation, security regression checks, and independent review exist. A verified policy seam does not justify claiming autonomous code self-repair.

## Partial fan-out failure

When one branch raises, the graph may not return reliable receipts for sibling branches even if some sibling artifacts were written. The conservative authority transition is to mark all still-`running` tasks in that fan-out `needs_review`, preserve any artifacts as evidence, and forbid automatic rerun. An operator or later recovery policy can reconcile receipts without inventing completion or duplicating side effects.

## Evidence boundaries

Separate these claims:

- deterministic graph/checkpoint/locking tests prove runtime mechanics;
- a delegating recorder can prove a configuration reached the real executor while preserving the real execution path;
- a container receipt proves that container's boundary, not every future native executor adapter;
- typed intents prove reconciliation semantics, not natural-language interpretation quality;
- evidence-required completion proves a gate, not live research-source quality;
- SQLite plus an in-process lock proves a single-process pilot, not production multi-process durability.

## Pitfalls

- Treating checkpoint history as a transaction or queue.
- Holding the conversation lock throughout worker execution and thereby defeating live steering.
- Completing from a stale task dictionary after a new turn arrived.
- Testing only simultaneous starts, not completion/error merge races.
- Calling persisted configuration "effective" without observing the real consumer.
- Retrying `needs_review` work automatically after an ambiguous side effect.
