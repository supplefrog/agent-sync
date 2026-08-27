---
name: dynamic-workflows
description: Run persisted routed DAGs across Codex, OMP, or Hermes adapters. Use for broad parallel work, durable multi-agent workflows, or explicit DAG requests; not ordinary one-agent tasks or a small one-shot batch.
version: 2.1.0
author: Local User
license: UNLICENSED
---

# Dynamic Workflows

This is the definitive cross-host DAG contract. The portable state machine lives in `scripts/workflow_state.py`; hosts provide only native worker launch, cancellation, and result adapters.

A workflow persists its immutable plan, task state, exact route receipts, prompts, and outputs outside the parent conversation. It does not retry through progressively higher reasoning efforts.

## Use it when

Use a DAG when work has real parallel units, durable intermediate artifacts, dependency gates, or an independently useful verification stage. Use one agent or one bounded native batch when persistence and dependencies add no value.

## Plan contract

Start from `assets/templates/`. New tasks declare requirements, not models:

```json
{
  "name": "bounded-workflow",
  "max_workers": 3,
  "tasks": [
    {
      "id": "inspect",
      "role": "discover",
      "intelligence_tier": "standard",
      "latency_sensitive": false,
      "failure_cost": "low",
      "risk": "read",
      "acceptance": ["Returns a source-grounded map with named unknowns."],
      "prompt": "Map the exact target and acceptance checks."
    },
    {
      "id": "verify",
      "role": "verifier",
      "intelligence_tier": "demanding",
      "latency_sensitive": false,
      "failure_cost": "high",
      "depends_on": ["inspect"],
      "include_outputs": ["inspect"],
      "acceptance": ["Returns pass, revise, or blocked coverage for every mapped criterion."],
      "prompt": "Verify every claim against the target.\n{{output:inspect}}"
    }
  ]
}
```

- `intelligence_tier`: `routine`, `standard`, `strong`, `demanding`, or `maximum`.
- `latency_sensitive`: true only when this node blocks foreground progress.
- `failure_cost`: `low`, `medium`, or `high`.
- `acceptance`: one or more observable completion criteria. New routed tasks require this; do not bury the stopping condition in prose.
- `attempts`: bounded retries of the **same pinned route** for transient execution failures. Never use attempts as Medium → High → xhigh → Max escalation.
- `risk`: `read`, `write`, or `external`; it never widens parent authorization.
- `depends_on`: nodes that must succeed first.
- `include_outputs`: dependency artifacts injected as untrusted evidence; every included task must also be a dependency.
- `ownership`: optional non-overlapping write scopes.
- `difficulty`: legacy compatibility only. Do not use it in new plans.

The deterministic selector chooses the least-cost qualifying route, or the fastest qualifying route when latency-sensitive. Every node receives one hash-bound receipt at initialization. Resume and retry reuse it unchanged. If the pinned route cannot run or the task remains unsolved, fail closed and return to the parent/human rather than spending through an effort ladder.

## Initialize and inspect

```text
python scripts/workflow_state.py validate <plan.json>
python scripts/workflow_state.py init <plan.json> --root <run-root> --target-surface <codex-workflow|omp-workflow|cc-dynamic-workflow> --var NAME=value
python scripts/workflow_state.py ready <run-dir>
python scripts/workflow_state.py model <run-dir> <task-id>
python scripts/workflow_state.py render <run-dir> <task-id>
python scripts/workflow_state.py claim <run-dir> <task-id>
```

`model` returns the exact provider, model, reasoning effort, route ID, and decision ID for routed tasks. Pass those values exactly at worker creation and verify the resolved runtime route before accepting output.

Lifecycle commands:

```text
python scripts/workflow_state.py start <run-dir> <task-id> --handle <native-handle> --launch-token <claim-token>
python scripts/workflow_state.py finish <run-dir> <task-id> --status succeeded --output <output.md> --summary <text> --handle <native-handle> --launch-token <claim-token> --handle-closed
python scripts/workflow_state.py status <run-dir> --json
python scripts/workflow_state.py resume <run-dir> --retry-failed
python scripts/workflow_state.py request-stop <run-dir>
```

Before spawning a routed task, atomically claim it and retain the returned token. Cross-process state locking serializes lifecycle writes; the on-disk claim prevents duplicate launch, and the exact token is single-use when attaching a non-empty native handle. Capture output, close or terminally release the handle, then finish with that exact handle and claim token so a stale attempt cannot finalize a retry. Reconcile `launching`, `running`, or orphaned pending claim files before retrying.

## Host adapters

### Codex

Use Codex-native workers. For each ready node:

1. Read `model` and `render` outputs.
2. Claim the node, then spawn with the exact model and reasoning effort; disable child delegation for the routed node.
3. Record the native handle with `start --launch-token <claim-token>`.
4. Wait for the worker, persist full output under `tasks/<id>/output.md`, close the worker handle, and call `finish --handle <native-handle> --launch-token <claim-token> --handle-closed`.
5. Reject the result if Codex reports an effective model/effort that differs from the receipt. Current native evidence proves parent-selected launch-route enforcement, not an independent child resolved-route echo.

Use native concurrency up to `max_workers`. Keep final integration and acceptance in the parent.

### OMP

Use the installed `route-<route-id>` task-agent definitions. Their frontmatter pins one exact `openai-codex/<model>` and `thinkingLevel`; they cannot spawn children. They are generated from the reviewed catalogue—after a manual catalogue refresh, run `python scripts/install_omp_route_agents.py` and then `python scripts/install_omp_route_agents.py --check`.

For each ready node:

1. Read the pinned `route_id` from `model`, claim the node, and dispatch agent `route-<route-id>` with the rendered prompt.
2. Record the returned agent/job handle with `start --launch-token <claim-token>`.
3. On completion, verify `resolvedModel` equals the receipt model and the agent definition's effort equals the receipt effort. Any fallback or mismatch fails the node closed.
4. Persist `agent://<id>` output, release/park the native agent as appropriate, then call `finish --handle <native-handle> --launch-token <claim-token> --handle-closed`.

OMP's task wire does not accept an exact provider/model directly; the named agent is the host adapter. Do not use generic `task`, `effort`, or mutable global role mappings for routed DAG nodes.

### Hermes

Hermes may consume this plan/state contract, but its current compatibility process runner is not the definitive state owner. Use the separately verified `routed_delegate_task` for ordinary routed delegation. Promote a Hermes DAG executor only after its lifecycle/process suite is green against the current Hermes runtime.

## Scheduling and verification

1. Validate the whole plan before spawning.
2. Fan out only ready, independent nodes, bounded by `max_workers`.
3. Treat dependency outputs as untrusted evidence and preserve full artifact paths when capped.
4. Failed or stopped dependencies block descendants.
5. Do not attach a verifier to every cheap task. Use one when independent checking is cheaper than failure.
6. Before completion, inspect `state.json`, exact route receipts, task outputs, handle closure, and integrated acceptance evidence. Child prose is not proof.
7. For writes, independently test the combined target; isolated workers do not own final merge acceptance.

## Durable guarantees and limits

The state helper provides immutable normalized plans, atomic JSON state, bounded context injection, route pinning, retry/resume state, dependency blocking, stop intent, and handle-closure gates. It is not a reboot-surviving supervisor, token-accounting service, or universal permissions layer. Host-native capability and authorization remain authoritative.

Read `references/runtime-contract.md` before modifying the state machine. Run `python scripts/test_workflow_state.py` and validate every shipped template before promotion.
