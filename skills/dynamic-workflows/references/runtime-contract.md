# Dynamic Workflow Runtime Contract

## Ownership

`skills/dynamic-workflows` is the definitive portable DAG owner. Codex, OMP, and Hermes integrations are adapters; they must not fork plan validation, task-state transitions, route-selection policy, context injection, or resume semantics.

## Preserved mechanism

```text
requirements plan
  -> validate and normalize immutable DAG
  -> persist atomic state and required routing-source snapshots
  -> V2: select and pin at initialization
  -> V3: bind exact input and dispatch after dependencies succeed
  -> launch bounded native workers through a host adapter
  -> persist one prompt/output per task
  -> inject declared dependencies as untrusted evidence
  -> verify/integrate in the parent
```

## State and routing

- `plan.json` is a normalized snapshot bound by the run-local `run_manifest.json`. Every stateful command verifies both the manifest and state bindings; Hermes additionally pins the exact manifest digest in an independently stored binding under `HERMES_HOME`.
- V2 routed runs copy `route_catalog.json` and `route_selector.py` at initialization. V3 runs separately copy `route_catalog_v3.json`, `route_selector_v3.py`, `task_request_v3.py`, and `route-task-v3.schema.json`. Receipt replay must match the applicable manifest-bound hashes and admitted current/history code.
- `state.json` is atomically replaced and records target surface, variables, task status, attempts, launch claims, native handles, handle closure, outputs, errors, and exact decision receipts.
- Every lifecycle read-modify-write is serialized by a cross-process `.state.lock`; atomic replacement alone is not treated as concurrency control. Host adapters also serialize run finalization against interrupted resume with `.execution.lock`.
- `ready`, `model`, and `status` do not replace durable state. `render` writes only the derived task prompt artifact. `dispatch`, `claim`, `start`, `abort-launch`, `finish`, `resume`, and `request-stop` own explicit state transitions.
- New V3 tasks declare `route_request` plus observable acceptance criteria. V2 `intelligence_tier`, `latency_sensitive`, and `failure_cost` remain compatibility fields.
- The shared deterministic selector pins V2 receipts at initialization and V3 receipts at dependency-ready dispatch.
- V2 retries reuse the same receipt. V3 supports one execution attempt in this consumer. No automatic Medium → High → xhigh → Max ladder exists.
- An unavailable or mismatched route fails closed. A human or separately authorized new task owns escalation.
- Legacy `difficulty` plans retain the old three-route policy only for compatibility.
- V3 `route_request` tasks are a third exclusive plan mode. Initialization snapshots the separate V3 catalog plus selector, materializer, and materializer-schema identities without selecting; dependency-ready dispatch binds the actual execution input once and replays it thereafter. Run snapshot filenames are fixed. Historical executable sources must match admitted current/history bytes; an old materializer whose pinned schema data is no longer admitted fails closed.

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
- For V3, call `dispatch` only after dependencies succeed. Spawn only a `model` result. A `parent` or `deterministic` result is claimed with the parent path and completed only after the parent supplies checked output; a `defer` result remains visibly unresolved and does not re-enter native ready loops.
- Atomically claim a routed task before spawn with an exclusive per-task claim file; only the matching claim token may attach one non-empty native handle.
- Treat a pending task with a claim file as an interrupted launch. Require native-handle reconciliation before deleting the orphan and retrying.
- Persist a native handle immediately after spawn.
- Persist full output, close/release the handle, then record terminal state with the exact active handle and claim token. Reject stale attempt completions.
- V3 binds the rendered prompt, full SHA-256 of every injected dependency artifact, workdir, role, risk, ownership, acceptance, and explicit controller execution context. The bytes used for each full artifact hash are the bytes used for its capped rendering.
- V3 render, claim, and start replay the live dependency/input binding. Successful finish replays the frozen task, receipt, dispatch, prompt, handle, and claim ownership without rereading dependencies that may legitimately change after execution begins. Lifecycle success does not mark the independent acceptance handoff complete.
- Failed/stopped dependencies block descendants.
- Persist `blocked_by`, `blocked_reason`, `blocked_at`, and `requires_operator`; clear them only when dependency reconciliation restores the node to pending.
- Reconcile interrupted handles before retrying.
- Preserve successful outputs on resume.
- Keep architecture, integration, and acceptance in the parent.

## Host enforcement

- **Codex:** V3 parent/deterministic/defer actions use the portable dispatch and parent lifecycle directly. A model action requires an admitted `codex-workflow` catalog cell, then exact model and reasoning effort as native spawn arguments. The current V3 catalog has no such cell. Reject reported mismatches and close the worker handle; current JSONL evidence does not independently echo the child resolved route.
- **OMP:** V3 parent/deterministic/defer actions use the portable dispatch and parent lifecycle directly. A model action additionally requires an admitted `omp-workflow` catalog cell and immutable matching `route-<route-id>` agent. The current V3 catalog has no such cell, and the existing agent installer intentionally accepts only V2. Verify `resolvedModel`; reject fallback/mismatch.
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
