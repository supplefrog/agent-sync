# Kanban authority and safe dispatch

Use this for durable Hermes task orchestration across threads or agent hosts.

## State model

- Kanban is the sole task authority; sessions and threads are evidence containers.
- A Kanban parent link is an **execution prerequisite**, not a goal-grouping edge. The child cannot run until every parent is done or archived.
- Represent ongoing or never-ending goals as non-dispatching authority/receipt cards. Represent executable work as bounded leaf cards. Keep broader-goal membership in metadata/comments/reconciliation artifacts unless it is a real dependency.
- Dispatch, claim, spawn, heartbeat, execution, completion, artifact delivery, and reconciliation are distinct states. `spawned` is not proof of execution; require running state plus PID/heartbeat or equivalent live evidence.

## Before release

For every executable card, verify:

1. bounded outcome and measurable acceptance checks;
2. explicit assignee/profile;
3. correct persistent `dir:` or isolated `worktree:` workspace when outputs must survive; avoid scratch for durable deliverables;
4. required current skill owners, especially after curator consolidation/renames;
5. runtime, retry, and idempotency bounds;
6. dependency direction against actual Kanban semantics;
7. no competing worker owns the same writable directory.

Do not unblock migrated placeholders blindly. Archive or retain them as receipts, then create idempotent executable replacements when their contract, workspace, or ownership is underspecified.

## Safe queueing

### Autonomous low-token board care

- For a material orchestration or automation change, load `outcome-first-workflow-design` before implementation and inspect enabled skills plus Hermes's native dispatcher, lifecycle hooks, review path, notifications, and script-only cron. Extend the smallest supported owner; do not invent another board, watcher, or scheduler first.
- Do not use a standing `/goal` loop to watch Kanban. Goal mode iterates one session/card and invokes a judge per turn; it neither claims nor moves unrelated board work.
- Keep normal scheduling in the gateway dispatcher. It consumes no model tokens while idle and already owns dependency promotion, claims, retries, stale-worker recovery, and review dispatch.
- Use `kanban_task_blocked` lifecycle hooks for immediate intervention signals. Create one bounded caretaker card per actionable source episode with an event-scoped idempotency key. Exclude dependency waits and caretaker-authored cards to prevent recursion.
- Treat the idempotency key as identity metadata, not an atomic guarantee: current Kanban persistence can accept concurrent duplicate inserts. Serialize the check/create boundary across hook and repair processes with a bounded OS-backed lock, then re-check inside the lock before creating. Regression-test simultaneous contenders.
- Respect cross-card authority. A delegated caretaker may inspect and comment on its source but must not bypass the worker guard to change another card's status. The parent/operator owns the final source transition and must honor task judges.
- Accept a clear resolution handoff only from a successful caretaker-owned run whose exact event-scoped idempotency key matches the still-current source event. Do not trust a marker in an arbitrary source comment. A structured `keep_blocked` result records a valid gate without waking the user.
- Surface a user question only when a caretaker blocks with the exact ambiguity marker. Operational failures, cross-card guard messages, or generic blocked reasons are not user decisions. Parent-turn hooks must exclude both dispatcher-owned Kanban workers and in-process delegated children; use Hermes's context predicate as well as the subprocess environment marker.
- Use a slow script-only/no-agent cron scan only as repair for events missed while the plugin or gateway was offline. The script may create missing idempotent caretaker cards directly; it must not poll with an LLM or duplicate the dispatcher. Create recurring schedules in recurring form (for example, `every 30m`) and read back that the repeat limit is infinite/null; editing a one-shot schedule can retain its finite repeat count.
- Normal completion should not create a caretaker card when native dependent promotion is sufficient. Spend a caretaker turn only on actionable blocked/triage/review states or independently proven reconciliation work.
- A caretaker resolves clear causes through supported board/repository surfaces. If one user decision materially changes the correct action, persist one concise question and inject/surface only that question on the next user-driven turn; do not dump board state or ask the user to inspect it.
- Plugin lifecycle hooks fire only in processes that have discovered plugins (gateway/worker sessions do). A standalone `hermes kanban block` process is not sufficient proof of hook delivery. Verify the hook through a preloaded plugin lifecycle dispatcher under an isolated `HERMES_HOME`; separately prove the script-only repair path and idempotency.

### Dispatch release

- Automatic rolling requires all three: `kanban.dispatch_in_gateway=true`, a live dispatcher that owns the board, and the global emergency pause lifted. A running gateway or ticker is not proof of dispatch; inspect board diagnostics and prove behavior by observing an eligible ready card transition to running without a manual dispatch.
- The embedded dispatcher snapshots Kanban config at gateway boot. After changing dispatch flags, intervals, or concurrency caps, restart the gateway from an independent shell outside the gateway process tree; a gateway-descendant terminal is correctly refused because restart would terminate its own command.
- After restart, verify the new gateway PID, singleton dispatcher-lock ownership, effective concurrency value in the gateway log, and one real automatic ready→running transition.
- Set the per-profile concurrency cap to the number of genuinely independent resource lanes, not the backlog size.
- Run cards concurrently only when their writable repositories, live profile/config surfaces, and external mutation domains are isolated. Normalize effective writable roots before claim and serialize identical roots with a real prerequisite/lease; priority and per-profile concurrency are not locks. Prove a baseline commit before selecting a Git worktree. For uncommitted repositories, serialize or use a runtime-owned temporary copy with explicit integration and cleanup receipts.
- Dry-run dispatch first. Confirm which card would spawn and why others are held.
- Before assignment or release, inspect the live assignee registry and require an on-disk/spawnable profile. A name present only because stranded cards reference it is not a worker. If an actionable lane is assigned to a phantom profile, reassign through the supported operator surface and verify the subsequent claim; do not report it as working.
- Read back task state, run row, PID, heartbeat, workspace, and loaded skills after every release.
- Before resuming a waiting card, prove that its workspace exists, is the intended repository/ref, and does not mix unrelated writable changes. A stale or wrong workspace is a control-plane defect, not a worker problem. Retarget through the current supported operator/kernel workspace setter, append an audit comment when the setter emits no event, and read back the path before dispatch. Prefer a clean current-main worktree for divergent lifecycle work; never overwrite or silently reuse an unrelated dirty checkout.
- When repeated blocking routes a fully specified card to `triage`, do not rewrite its specification merely to escape the state and never update SQLite directly. Revalidate the event-bound recommendation against source acceptance evidence and use the supported operator transition. If the public specifier is unavailable or would rewrite an already-complete spec, inspect the current Kanban kernel and use its documented status-only triage transition when one exists (for example, `specify_triage_task` with no title/body mutation); then read back the unchanged spec, resulting state, and event before dispatch. Submit the ordinary completion transition so the native judge still decides. If the judge rejects, preserve the rejection and resume correction work.
- A broad orchestrator card should not be completed merely to release its work. Remove false prerequisite links or replace them with real execution cards.

## Contextual intake and change admission

- Treat each natural user statement as evidence of an outcome, not automatically as a command or new card. Reconcile the current request with the user profile/card, relevant session history, live board ownership/dependencies, and live capability state. Classify it as conversation only, durable preference, update to an existing card, new bounded card, dependency/priority change, or one genuine decision.
- Do not create work from reflection, speculation, or an already-satisfied outcome. Preserve the source statement and why it changed the board. Deduplicate by intended outcome and current state, not title similarity.
- The fixed objective is higher verified outcome quality at lower total expected cost. A user suggestion is a candidate change, not automatic evidence that another instruction, skill, task, or mechanism is beneficial. Apply the existing outcome/evaluation gate; count model use, latency, retries, prompt load, verification, maintenance, and failure cost. Retain, simplify, remove, or make no change when that wins.
- External skill/plugin discovery is one bounded source inside the existing research-before-building workflow, not a separate universal layer. Use `external-skill-intake` when a material, novel, risky, or recurring outcome could plausibly benefit. Skip catalog search for routine, one-off, or already-well-owned work. Cheaply reject weak/overlapping candidates before paying for staged behavioral verification; fully evaluate only finalists that could beat the baseline and amortize their admission cost through reuse or avoided failure.

## Completion receipt and delivery

Every completed orchestration task must persist a concise receipt stating:

1. what changed or was decided;
2. how it was accomplished at a useful level;
3. what checks or external readback verified it;
4. what was not done, remains uncertain, or still needs a decision;
5. the durable task/evidence handle when useful.

Persistence and interruption are different. Put detailed evidence on the card and route routine receipts to an on-demand or batched digest; do not push each completion into the user chat unless requested. Only a genuine unresolved decision interrupts immediately. When a receipt is delivered, keep it readable: do not send status-only `done`, raw reviewer language, unexplained internal terms, or a process transcript.

## Completion and cleanup

- Reconcile worker claims against artifacts, tests, external readback, and native stores before accepting completion.
- A thread-local implementation, even with passing narrow tests, is partial evidence until compared against the broader outcome contract, competing and lateral implementations, held-out cases, and regressions. Retain, adapt, absorb, supersede, or reject it based on that whole-task review.
- Do not use repeated `block` transitions as a review protocol. When the native review state and worker handoff are available, submit a structured producer receipt to `review`; an independent reviewer then accepts to `done` or returns the same card to `ready` with one bounded correction. Run deterministic checks before invoking a reviewer model. If the native path is unavailable, use one separate verifier card or one parent review—never a caretaker exception loop. A fully verified legacy card in triage may be archived with an independent receipt only when direct completion is unsupported and archived prerequisites correctly release children.
- A thread may be retired only after its complete user intention—including lateral, partial, or superseding work—is independently verified complete and useful evidence is integrated.
- Never delete active, shared, referenced, ambiguous, or partially complete threads. Use supported lifecycle controls; if deletion is unavailable, close/release and retain only the distilled evidence handle.
