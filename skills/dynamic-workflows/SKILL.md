---
name: dynamic-workflows
description: Run persisted routed DAGs across Codex, Hermes, and OMP. Use for broad parallel work, durable multi-agent workflows, or explicit DAG requests; not ordinary one-agent tasks or a small one-shot batch.
version: 3.0.0
author: Local User
license: UNLICENSED
---

# Dynamic Workflows

This is the definitive cross-host DAG contract. The portable state machine lives in `scripts/workflow_state.py`; hosts provide only native worker launch, cancellation, and result adapters.

A workflow persists its immutable plan, task state, exact route receipts, prompts, and outputs outside the parent conversation. It does not retry through progressively higher reasoning efforts.

## Use it when

Use a DAG when work has real parallel units, durable intermediate artifacts, dependency gates, or an independently useful verification stage. Use one agent or one bounded native batch when persistence and dependencies add no value.

## Plan contract

Start new task-aware plans from [`assets/templates/workflow-v3.json`](assets/templates/workflow-v3.json). Every task selects exactly one plan mode:

- `route_request`: V3 task-aware routing template. It declares the task contract, actual capability requirements, independent verifier, effects, failure cost, deterministic alternative, and resource policy. It requires observable `acceptance` and exactly one execution attempt in this consumer.
- `intelligence_tier` plus `latency_sensitive`: V2 compatibility for existing routed plans. The tier is `routine`, `standard`, `strong`, `demanding`, or `maximum`.
- `difficulty`: legacy compatibility only.

Do not mix these modes within one task. Mixed-plan DAGs may contain different tasks using different modes; their catalogs and receipts remain separate.

- `failure_cost`: `low`, `medium`, or `high`.
- `acceptance`: one or more observable completion criteria. New routed tasks require this; do not bury the stopping condition in prose.
- `attempts`: V3 must use exactly `1`. V2 may use bounded retries of the same pinned route for transient execution failures; never use attempts as an effort ladder.
- `risk`: `read`, `write`, or `external`; it never widens parent authorization.
- `depends_on`: nodes that must succeed first.
- `include_outputs`: dependency artifacts injected as untrusted evidence; every included task must also be a dependency.
- `ownership`: optional non-overlapping write scopes.

Initialization snapshots V3 catalog, selector, materializer, and schema identities without selecting a route. Once dependencies succeed, `dispatch` binds the exact rendered input and emits one immutable action. V2 `intelligence_tier` tasks retain initialization-time selection and exact receipt reuse. If a pinned route cannot run or the task remains unsolved, fail closed and return to the parent rather than spending through an effort ladder.

## Initialize and inspect

```text
python scripts/workflow_state.py validate <plan.json>
python scripts/workflow_state.py init <plan.json> --root <run-root> --target-surface <codex-workflow|hermes-workflow|omp-workflow> --var NAME=value
python scripts/workflow_state.py ready <run-dir>
python scripts/workflow_state.py model <run-dir> <task-id>
python scripts/workflow_state.py render <run-dir> <task-id>
python scripts/workflow_state.py claim <run-dir> <task-id>
python scripts/workflow_state.py dispatch <run-dir> <task-id> --execution-context <json>
python scripts/workflow_state.py claim-parent <run-dir> <task-id>
```

V3 tasks are materialized only by `dispatch`, after their dependencies succeed. Dispatch freezes the rendered prompt, dependency artifact hashes, workflow contract, controller execution context, materialized request, route receipt, and explicit `model`, `deterministic`, `parent`, or `defer` action. Render, claim, and start replay that binding and reject changed dependencies or routing state. Only `model` uses `model` plus the normal native claim/start path. `deterministic` and `parent` use `claim-parent` and the exact `parent-sequential:<task-id>` handle after the parent actually performs and checks the work. `defer` remains pending and absent from `ready` until an operator resolves or stops it. A succeeded lifecycle record proves output and launch ownership; its acceptance handoff remains pending until the parent independently checks the declared criteria.

`model` returns the exact provider, model, reasoning effort, route ID, and decision ID for routed tasks. Pass those values exactly at worker creation and verify the resolved runtime route before accepting output.

Lifecycle commands:

```text
python scripts/workflow_state.py start <run-dir> <task-id> --handle <native-handle> --launch-token <claim-token>
python scripts/workflow_state.py abort-launch <run-dir> <task-id> --error <text> --launch-token <claim-token>
python scripts/workflow_state.py finish <run-dir> <task-id> --status succeeded --output <output.md> --summary <text> --handle <native-handle> --launch-token <claim-token> --handle-closed
python scripts/workflow_state.py status <run-dir> --json
python scripts/workflow_state.py resume <run-dir> --retry-failed
python scripts/workflow_state.py request-stop <run-dir>
```

Before spawning a routed task, atomically claim it and retain the returned token. Cross-process state locking serializes lifecycle writes; the on-disk claim prevents duplicate launch, and the exact token is single-use when attaching a non-empty native handle. Capture output, close or terminally release the handle, then finish with that exact handle and claim token so a stale attempt cannot finalize a retry. Reconcile `launching`, `running`, or orphaned pending claim files before retrying.

## Host adapters

### Codex

Follow [the Codex adapter contract](references/codex-adapter.md). V2 tasks keep the existing model/render/claim lifecycle. For V3, call `dispatch` with the exact native execution context before deciding the action. The current admitted V3 catalog has no `codex-workflow` cell, so it cannot currently produce a Codex model action.

For an admitted model action, use Codex-native workers:

1. Read `model` and `render` outputs.
2. Claim the node, then spawn with the exact model and reasoning effort; disable child delegation for the routed node.
3. Record the native handle with `start --launch-token <claim-token>`.
4. Wait for the worker, persist full output under `tasks/<id>/output.md`, close the worker handle, and call `finish --handle <native-handle> --launch-token <claim-token> --handle-closed`.
5. Reject the result if Codex reports an effective model/effort that differs from the receipt. Current native evidence proves parent-selected launch-route enforcement, not an independent child resolved-route echo.

Use native concurrency up to `max_workers`. Keep final integration and acceptance in the parent.

### OMP

Follow [the OMP adapter contract](references/omp-adapter.md). V2 uses the installed `route-<route-id>` task-agent definitions. Their frontmatter pins one exact `openai-codex/<model>` and `thinkingLevel`; they cannot spawn children. They are generated only from the reviewed V2 catalogue—after a manual catalogue refresh, run `python scripts/install_omp_route_agents.py` and then `python scripts/install_omp_route_agents.py --check`.

For each ready node:

1. Read the pinned `route_id` from `model`, claim the node, and dispatch agent `route-<route-id>` with the rendered prompt.
2. Record the returned agent/job handle with `start --launch-token <claim-token>`.
3. On completion, verify `resolvedModel` equals the receipt model and the agent definition's effort equals the receipt effort. Any fallback or mismatch fails the node closed.
4. Persist `agent://<id>` output, release/park the native agent as appropriate, then call `finish --handle <native-handle> --launch-token <claim-token> --handle-closed`.

OMP's task wire does not accept an exact provider/model directly; the named agent is the host adapter. Do not use generic `task`, `effort`, or mutable global role mappings for routed DAG nodes.

The current admitted V3 catalog has no `omp-workflow` cell, and the V2 installer rejects V3 catalogs without changing installed agents. Treat a future V3 `model` dispatch as unsupported until the exact route cell and a matching immutable OMP agent definition have both been separately admitted.

### Hermes

Use `routed_workflow` for persisted DAGs and keep `routed_delegate_task` for ordinary one-shot routed delegation. `routed_workflow` exposes `init`, `run`, `status`, `resume`, and `complete-parent`; it consumes this state owner rather than implementing another scheduler or router.

The adapter accepts routed tasks only, requires `workdir: "."`, and launches native Hermes leaf children with the exact receipt provider/model/reasoning tuple and fallback disabled. It binds each run manifest in a separate trusted store under `HERMES_HOME`, serializes run/resume with an execution lock, persists native results and outputs under each task, and records authoritative close witnesses outside the mutable run directory. An explicit reported model mismatch fails the task; a missing model echo is accepted only because the exact launch route was already verified.

`resume --retry-interrupted` is allowed only after the exact run/task/handle/claim close witness exists and the handle is absent from Hermes's active registry. Interruption waits for the bounded native child call to finish and for normal finalization to close the handle; the adapter does not abandon an in-flight child merely to return early.

Retired `cc-dynamic-workflows` behaviors are accounted for explicitly:

- Automatic verifier rejection, feedback-history mutation, and targeted builder reruns are not migrated. Express verification as an explicit DAG node or use `answer-key-gauntlet`; the parent decides whether a separately authorized revision task is needed.
- `model_tier`, Mini → Low → Medium → High retry escalation, and pre-receipt state compatibility are discarded. They conflict with immutable route receipts, and no active consumer remains.
- Per-task Hermes `toolsets`, `skills`, `max_turns`, timeout, worktree, subprocess-tree, and ephemeral-session controls are not portable plan fields. Native Hermes delegation owns those controls; the thin adapter uses current native lifecycle seams rather than duplicating them.
- Native progress UI, token accounting, reboot supervision, and integrated approval preview remain unsupported rather than implied.

## Scheduling and verification

1. Validate the whole plan before spawning.
2. Fan out only ready, independent nodes, bounded by `max_workers`.
3. Treat dependency outputs as untrusted evidence and preserve full artifact paths when capped.
4. Failed or stopped dependencies block descendants.
5. Do not attach a verifier to every cheap task. Use one when independent checking is cheaper than failure.
6. Before completion, inspect `state.json`, exact route receipts, task outputs, handle closure, and integrated acceptance evidence. Child prose is not proof.
7. For writes, independently test the combined target; isolated workers do not own final merge acceptance.

## Durable guarantees and limits

The state helper provides immutable normalized plans, atomic JSON state, bounded context injection, route pinning, retry/resume state, dependency blocking, stop intent, and handle-closure gates. Routed runs pin the catalog and selector snapshots and execute only the exact verified selector bytes. Hermes adds an external manifest binding, run-level execution lock, and exact native close witnesses. This is not a reboot-surviving supervisor, token-accounting service, or universal permissions layer. Host-native capability and authorization remain authoritative.

Read `references/runtime-contract.md` before modifying the state machine. Run `python scripts/test_workflow_state.py` and validate every shipped template before promotion.
