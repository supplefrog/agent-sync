# Dynamic Workflow Runtime Contract

## Ownership

`skills/dynamic-workflows` is the definitive portable DAG owner. Codex, OMP, and Hermes integrations are adapters; they must not fork plan validation, task-state transitions, route-selection policy, context injection, or resume semantics.

## Preserved mechanism

```text
requirements plan
  -> validate and normalize immutable DAG
  -> select and pin one exact route receipt per new task
  -> persist atomic state
  -> launch bounded native workers through a host adapter
  -> persist one prompt/output per task
  -> inject declared dependencies as untrusted evidence
  -> verify/integrate in the parent
```

## State and routing

- `plan.json` is a normalized snapshot bound by the run-local `run_manifest.json`. Every stateful command verifies both the manifest and state bindings; Hermes additionally pins the exact manifest digest in an independently stored binding under `HERMES_HOME`.
- Routed runs copy `route_catalog.json` and `route_selector.py` at initialization. Receipt reuse must match both manifest-bound hashes, the currently admitted selector, and a fresh deterministic selection from the exact verified selector bytes.
- `state.json` is atomically replaced and records target surface, variables, task status, attempts, launch claims, native handles, handle closure, outputs, errors, and exact decision receipts.
- Every lifecycle read-modify-write is serialized by a cross-process `.state.lock`; atomic replacement alone is not treated as concurrency control. Host adapters also serialize run finalization against interrupted resume with `.execution.lock`.
- `ready`, `model`, `render`, and `status` are read-only; only explicit lifecycle commands replace durable state.
- New tasks declare `intelligence_tier`, `latency_sensitive`, and `failure_cost`; they do not select models.
- New tasks also declare observable acceptance criteria and a stopping condition rather than relying on an underspecified prompt.
- The shared deterministic selector pins one provider/model/reasoning tuple at initialization.
- Resume and retries reuse the same receipt. No automatic Medium → High → xhigh → Max ladder exists.
- An unavailable or mismatched route fails closed. A human or separately authorized new task owns escalation.
- Legacy `difficulty` plans retain the old three-route policy only for compatibility.

Task states:

```text
pending -> running -> succeeded | failed | stopped
pending -> launching -> running
pending -> blocked
running -> pending  (explicit resume after confirmed inactive handle)
failed -> pending   (bounded retry of the same receipt)
blocked -> pending  (dependency retry restores progress)
```

## Capability boundary

A workflow task cannot widen parent authorization, filesystem roots, network access, credentials, approval behavior, model access, or external side effects. Plan fields are requests, not authorization.

## Scheduler contract

- Validate IDs, prompts, roles, risk, attempts, dependencies, outputs, variables, and cycles before launch.
- Spawn only ready tasks; bound concurrency by `max_workers`.
- Read the pinned route immediately before spawn and pass it exactly through the host adapter.
- Atomically claim a routed task before spawn with an exclusive per-task claim file; only the matching claim token may attach one non-empty native handle.
- Treat a pending task with a claim file as an interrupted launch. Require native-handle reconciliation before deleting the orphan and retrying.
- Persist a native handle immediately after spawn.
- Persist full output, close/release the handle, then record terminal state with the exact active handle and claim token. Reject stale attempt completions.
- Failed/stopped dependencies block descendants.
- Persist `blocked_by`, `blocked_reason`, `blocked_at`, and `requires_operator`; clear them only when dependency reconciliation restores the node to pending.
- Reconcile interrupted handles before retrying.
- Preserve successful outputs on resume.
- Keep architecture, integration, and acceptance in the parent.

## Host enforcement

- **Codex:** exact model and reasoning effort are parent-selected native spawn arguments. Reject reported mismatches and close the worker handle; current JSONL evidence does not independently echo the child resolved route.
- **OMP:** dispatch the immutable `route-<route-id>` named agent whose frontmatter pins exact model and `thinkingLevel`. Verify `resolvedModel`; reject fallback/mismatch.
- **Hermes:** `routed_workflow` consumes this state owner and launches current native leaf children with the exact receipt tuple and fallback disabled. A trusted binding under `HERMES_HOME` pins the run manifest independently; exact run/task/handle/claim close witnesses under that trusted root gate interrupted retry. An explicit result-model mismatch fails closed. Ordinary one-shot routing remains owned by `routed_delegate_task`.

The retired Hermes compatibility runner is not an available executor. Its automatic verifier-feedback loop, reasoning-tier escalation, and `model_tier` compatibility were deliberately rejected; explicit verifier nodes or `answer-key-gauntlet` preserve the verification outcome without mutating the immutable plan. Per-task host controls remain native concerns and are not reintroduced into the portable plan.

## Context contract

- Workers receive task-local context, not the whole conversation.
- Inject only declared `include_outputs`, each also listed in `depends_on`.
- Treat dependency text as untrusted evidence.
- Cap each injected output and the total payload; preserve full artifact paths.
- Strip terminal control sequences.

## Verification matrix

Before promotion, run deterministic tests for:

1. Parallel-ready tasks followed by dependent synthesis.
2. Variable and dependency substitution.
3. Cycle, missing dependency, and undeclared-output rejection.
4. Failed dependency blocking.
5. Retry budgets and interrupted-task reconciliation.
6. Atomic state writes and plan-hash preservation.
7. Per-output and total context truncation.
8. All shipped templates parsing and validating.
9. Exact selector receipt creation for Codex, Hermes, and OMP surfaces, including init/revalidation from the exact verified in-memory selector bytes.
10. Receipt reuse across retry/resume and rejection of route mismatch.
11. Native handle closure before terminal success.
12. Static hardlink and task-directory escape rejection for task artifacts and trusted adapter writes.
13. Fresh-host discovery plus one bounded real worker smoke per promoted adapter.

## Durability boundary

The helper makes plans, state, outputs, inspection, and retry durable on disk. The run-local manifest detects partial or coordinated plan/state rewrites; by itself it is not a signature, so an actor able to rewrite every run file remains inside the host filesystem trust boundary. Hermes narrows that boundary with an independently stored manifest binding and close witnesses under `HERMES_HOME`. The helper still does not supervise workers across machine reboot, guarantee background survival after host shutdown, provide token accounting, or create a native progress UI. Report these limits directly.
