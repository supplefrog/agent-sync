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
- V3 `route_request` tasks are a third exclusive plan mode. Initialization snapshots the separate V3 catalog plus selector, materializer, and materializer-schema identities without selecting. Dependency-ready dispatch binds the actual execution input once and replays it thereafter. The Codex on-demand path also freezes a task-local catalog and native observation at that boundary. A later availability refresh applies only to unbound tasks. Historical executable sources must match admitted current/history bytes. An old materializer whose pinned schema data is no longer admitted fails closed.

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

- **Codex:** V3 parent/deterministic/defer actions use the portable dispatch and parent lifecycle directly. A model action requires an admitted `codex-workflow` catalog cell, then exact model and reasoning effort as native spawn arguments. Check the admitted route's current evidence and scope. Reject reported mismatches and verify handle closure or release through the Codex adapter before recording terminal workflow state.
- **OMP:** V3 parent/deterministic/defer actions use the portable dispatch and parent lifecycle directly. A model action additionally requires an admitted `omp-workflow` catalog cell and immutable matching `route-<route-id>` agent. The current V3 catalog has no such cell, and the existing agent installer intentionally accepts only V2. Verify `resolvedModel`; reject fallback/mismatch.
- **Hermes:** `routed_workflow` consumes this state owner and launches current native leaf children with the exact receipt tuple and fallback disabled. A trusted binding under `HERMES_HOME` pins the run manifest independently; exact run/task/handle/claim close witnesses under that trusted root gate interrupted retry. An explicit result-model mismatch fails closed. Ordinary one-shot routing remains owned by `routed_delegate_task`.

The retired Hermes compatibility runner is not an available executor. Its automatic verifier-feedback loop, reasoning-tier escalation, and `model_tier` compatibility were deliberately rejected; explicit verifier nodes or `answer-key-gauntlet` preserve the verification outcome without mutating the immutable plan. Per-task host controls remain native concerns and are not reintroduced into the portable plan.

## T3 and Paseo dispatch

### Choose a dispatcher and worker

An active T3 controller uses `t3-workflow` and discovers the available provider instances with T3’s `orchestrator_capabilities`. Use the exact available instance, model and advertised reasoning option. Keep T3’s inherited approval mode. A standalone controller can use its existing native adapter when it covers the task. Use `paseo-workflow` for shared delegation outside T3 when an eligible native route cannot provide the chosen worker. Use the existing Paseo skill to discover the configured local dispatcher and its saved worker profiles. Start the configured daemon on demand if it is stopped. Use the selected profile's exact model, effort and approval mode.

Match the task to the advertised worker capability and the user's request. Prefer the current agent when alternatives offer the same fit and launching a peer adds no value. Different workers on the same dispatcher share the same interface. The T3 target must already be available in T3. Preserve the approval and account boundaries.

This adapter currently accepts small inline text tasks with read risk, no tools or effects, one attempt and an independent complete verifier. Verify the whole native child activity, including any tools it actually used. Use a native adapter for tasks with tool or effect requirements that this dispatcher record cannot establish. Use subscription model targets from the configured workers and current positive quota in `codex-main`. Unknown costs require explicit route preference and a zero reserve, as in the V3 selector. Declare that preference as `["t3-dispatch"]` in T3 or `["paseo-dispatch"]` for the shared adapter. Match explicit model constraints against the native model ID, including any provider prefix.

### Refresh availability

Save the selected target from the live dispatcher in a local JSON file with these fields.

| Field | T3 | Paseo |
| --- | --- | --- |
| `dispatcher` | `t3` | `paseo` |
| `scope` | `environmentId:projectId:parentThreadId` | `serverId:workspaceId` from Paseo status and workspace list |
| `instance` | `providerInstanceId` | Configured provider ID |
| `model` | Advertised model ID | Profile model ID |
| `effort` | Selected advertised effort | Profile `thinkingOptionId` |
| `option` | Advertised option ID such as `reasoningEffort` | `thinkingOptionId` |
| `mode` | `inherit` | Profile `modeId` |

Run `python scripts/worker_dispatch.py prepare <target.json> --root <runs-root>/.worker-dispatch`, using the same runs root passed to `workflow_state.py init`. For T3 pass `--capabilities <readback.json>` from the active parent. The adapter returns a current observation, a single new probe, or a pending attempt. Save a new probe response as a local request file and launch it once using the instructions below. When the worker is terminal, save the app data to a result file and run `python scripts/worker_dispatch.py complete <cache-file> <attempt> <result.json>`. The challenge renews this exact target for 24 hours from the native observation. Reconcile a pending attempt with the dispatcher before launching more work. If native readback establishes that the probe failed or no child was created, clear it with `probe-failed <cache-file> <attempt> --reason <reason>`.

Use the same procedure for a probe and a task.

- **T3.** Send the returned command to the named native tool. Read the exact child task's `task_status` and its original thread's `t3_thread_read` with `view: activity`, `limit: 100` and `maxCharsPerItem: 20000`. Save the actual response objects as `{"environment": "<environmentId>", "status": <task_status>, "activity": <t3_thread_read>}`. The adapter checks the pinned parent, project, route, initial assignment, child run, terminal state and complete local activity. Keep normal T3 approvals.
- **Paseo.** Execute `python scripts/worker_dispatch.py paseo-launch <request.json> --home <configured-paseo-home>`. This starts the configured local daemon on demand and returns the Paseo agent ID. Once it settles, run `python scripts/worker_dispatch.py paseo-read <target.json> <agent-id> <request.json> --home <configured-paseo-home>` and save the result. The helper checks the exact agent and workspace, archives the settled agent and records the app status and logs. For a workflow task, use the existing `dispatcher-launch.json` as the request file.

The workflow relies on the controller collecting real app data. Route observations establish the application-selected route. T3 may omit the provider-reported executed model. Tool-free readback is a completion check. The dispatched worker still runs under the app's usual permissions, so keep assignments small and effect-free.

### Run and resume

1. Initialize with `--target-surface t3-workflow` or `--target-surface paseo-workflow`. For each ready task, use `dispatch --execution-context-file <context.json>` with the actual `active_t3` boolean, the `dispatcher_scope` identity and the `dispatcher_observation` returned by the refresh command.
2. Follow the normal parent or defer action when selected. For a model action, claim the task, then run `broker-launch <run> <task-id> --launch-token <token>`. For T3 supply `--capabilities` with current parent readback. The command saves the single launch intent and includes a unique attempt marker. Invoke it through the chosen app and immediately record the returned native handle with the normal `start` command and the same claim token.
3. If the launch response is lost, reconcile the existing child by the T3 request ID or the Paseo child assignment and title. Preserve an ambiguous claim until reconciliation. A deadline or approval is a pending state. Only abort a launch after native readback establishes that no child was created. Use native cancellation when stopping a child.
4. Save the app readback to `tasks/<task-id>/dispatcher-result.json` and its exact answer to the task output file. Finish with the original handle, claim token and `--handle-closed` once native work is terminal. The workflow checks the app data and binds the result and output bytes. Verify the result against the plan independently before using it.

A successful refresh can admit a new decision or renew an existing decision's exact launch target. Existing decisions retain their original target, evidence and transport. If the route expires before launch, refresh that same target and continue from the existing claim or decision. A resumed active child continues on its original dispatcher.

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
