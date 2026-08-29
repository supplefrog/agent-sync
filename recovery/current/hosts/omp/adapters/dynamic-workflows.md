---
name: dynamic-workflows
description: Run persisted routed DAGs in OMP for broad parallel work or explicit workflow requests; not ordinary one-agent tasks.
version: 2.1.0
---

# OMP Dynamic Workflows Adapter

Canonical owner: `{{agent-signal:AGENT_SIGNAL_ROOT}}/skills/dynamic-workflows/SKILL.md`.

Before using this capability, read the canonical skill and `references/runtime-contract.md`. Use its `scripts/workflow_state.py` for every plan/state mutation; do not duplicate or reinterpret the state machine.

Initialize with `--target-surface omp-workflow`. For every ready task:

1. Run `model` and `render` against the run directory, then atomically `claim` the task.
2. Dispatch OMP task agent `route-<route_id>` with the rendered prompt. These named agents pin the exact `openai-codex` model and `thinkingLevel` and cannot delegate.
3. Record the returned OMP agent/job handle with `start --launch-token <claim-token>`.
4. On completion, verify the result's `resolvedModel` equals the receipt model. Confirm the named agent file's `thinkingLevel` equals the receipt reasoning effort. A fallback or mismatch fails closed.
5. Persist the complete `agent://<id>` output to the task output path, release/park the native handle as appropriate, then call `finish --handle <native-handle> --launch-token <claim-token> --handle-closed`.

Use OMP batch task calls only for currently ready independent nodes and never exceed the plan's `max_workers`. Do not use generic `task`, a coarse per-call `effort`, mutable global role mappings, or sequential effort escalation for routed DAG nodes.

Treat `launching`, `running`, or a pending task with an orphan `launch.claim` as interrupted work after parent/process loss. Reconcile the native host before using `resume --retry-interrupted`; never delete or recreate a claim to guess that no worker exists. `start` requires the exact single-use claim token and a non-empty native handle.
