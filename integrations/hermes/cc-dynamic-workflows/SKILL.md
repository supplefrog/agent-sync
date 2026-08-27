---
name: cc-dynamic-workflows
description: Run Claude Code-style dynamic workflows from Hermes using an update-safe user skill and persistent local runner. Use only when the user explicitly asks for a workflow, dynamic workflow, ultracode, broad parallel audit/research/migration, or asks to save/rerun a multi-agent orchestration. Do not trigger for ordinary tasks that fit one agent or a small delegate_task batch.
version: 1.4.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [workflow, orchestration, fan-out, subagents, durable, claude-code-parity]
    related_skills: [delegation-workflows, code-change-verification]
---

# Claude-style Dynamic Workflows for Hermes

A dynamic workflow moves the plan, branching, and intermediate outputs out of the conversation and into a persisted run. Hermes then receives only the run status and final artifact. This avoids flooding one context window and makes the orchestration inspectable and rerunnable.

This is an update-safe compatibility layer, not native parity. It lives under the user skills directory and calls the public `hermes chat` CLI. Hermes updates do not overwrite custom skill names that are absent from the bundled manifest.

## What this provides

- A declarative DAG of Hermes agent tasks.
- Parallel execution with a bounded worker count.
- Per-task routing requirements, toolset, skill, workdir, timeout, max-turn, and worktree settings.
- With `automatic_routing: true`, the runner selects and pins each task's exact provider/model/reasoning tuple before launch; resume reuses that receipt without re-resolution.
- Legacy unreceipted plans retain the admitted low/medium/high policy only for backward compatibility. It is not a universal task-routing policy.
- Bounded escalation on child failure, timeout, or an explicit inability marker; receipt-pinned tasks do not silently switch routes.
- Optional per-task adaptive verification: a material rejection reruns only the rejected task at its next tier, then rechecks it.
- Atomic persisted state and one output file per task.
- Dependency-output injection for verifier and synthesis stages.
- Status, list, stop, and failed-task resume commands.
- Reusable workflow definitions under the user's Hermes home.

It does not provide Claude Code's native progress UI, isolated JavaScript runtime, token accounting, hundreds-agent scheduler, or restart-proof service. Those require a Hermes runtime feature.

## Paths

The runner is in this skill's `scripts/workflow_runner.py`.

Default durable data root:

```text
<HERMES_HOME>/workflows/
├── definitions/     # reusable plan JSON files
└── runs/            # run state and task outputs
```

Resolve relative skill paths against the skill directory injected by Hermes. Do not copy the runner into the Hermes source/install tree.

## Plan schema

Start from `templates/workflow.template.json` or one of the examples in `templates/`.

```json
{
  "name": "route-auth-audit",
  "description": "Audit route handlers and adversarially verify findings",
  "max_workers": 4,
  "automatic_routing": true,
  "tasks": [
    {
      "id": "discover",
      "role": "discover",
      "intelligence_tier": "routine",
      "latency_sensitive": false,
      "failure_cost": "low",
      "prompt": "List the route handlers to audit. Return paths and symbols only.",
      "workdir": ".",
      "max_turns": 20
    },
    {
      "id": "audit",
      "role": "explorer",
      "intelligence_tier": "strong",
      "latency_sensitive": false,
      "failure_cost": "high",
      "depends_on": ["discover"],
      "include_outputs": ["discover"],
      "prompt": "Audit the discovered handlers. Emit atomic file:line findings with evidence.",
      "max_turns": 40
    },
    {
      "id": "verify",
      "role": "verifier",
      "intelligence_tier": "strong",
      "latency_sensitive": false,
      "failure_cost": "high",
      "depends_on": ["audit"],
      "include_outputs": ["audit"],
      "verifies": ["audit"],
      "prompt": "Try to refute every finding. Reject audit only if it materially fails the evidence contract; otherwise keep findings that survive against the code.",
      "max_turns": 40
    }
  ]
}
```

Task fields:

- `id` and `prompt` are required.
- `depends_on`: task IDs that must succeed first.
- `include_outputs`: successful task outputs appended to the prompt. Each task must also appear in `depends_on`.
- `verifies`: optional task IDs adaptively checked by a `reviewer`, `verifier`, or `refuter`. Each target must be both a dependency and an included output. A target can have one adaptive verifier.
- `workdir`: absolute path or path relative to the plan file.
- `worktree`: run that task with `hermes chat --worktree`; use only in a git repo.
- `role`: `discover`, `reviewer`, `verifier`, `refuter`, `synthesizer`, `researcher`, `explorer`, or `worker`. Omitted roles default to `worker`.
- `intelligence_tier`: `routine`, `standard`, `strong`, `demanding`, or `maximum`; required when the plan sets `automatic_routing: true`.
- `latency_sensitive`: `true` only when this task blocks the user or a foreground dependency; required for automatic routing.
- `failure_cost`: `low`, `medium`, or `high`; defaults to `medium`.
- `task_class` and `verifier_plan`: optional receipt metadata.
- `model`, `provider`, `reasoning_effort`, `decision_receipt`: legacy/pre-materialized exact route fields. Do not set them in a new automatic plan; the runner writes them into its persisted plan before launch.
- `model_tier`: legacy fallback `mini`, `low`, `medium`, or `high` override when no decision receipt exists. Use `mini` only for brain-dead/mechanical work.
- `max_model_tier`: highest automatic escalation tier for legacy tier-routed tasks.
- `escalate`: bounded automatic escalation for legacy tier-routed tasks; disabled for receipt-pinned tasks.
- `toolsets`, `skills`, `max_turns`: optional public Hermes CLI controls.
- `timeout_seconds`: per-attempt wall-clock timeout, default 900.
- `attempts`: total attempt bound. When omitted on an escalating task, defaults to the number of reachable tiers.

For new plans, set top-level `automatic_routing: true` and classify each task's minimum intelligence tier and latency sensitivity. The runner calls `openai-delegation-route-research`, materializes the exact route and receipt, and pins them in `plan.json` and `state.json` before launching any child. Workflow roles do not choose models. Existing unreceipted plans retain the `mini`/`low`/`medium`/`high` role mapping only for backward compatibility.

Hermes `chat` exposes per-invocation model, provider, and reasoning. `scripts/tier_chat.py` remains a process-local compatibility adapter for the workflow child and never rewrites global `config.yaml`.

An escalating task advances `mini → low → medium → high` only when the child exits nonzero, exceeds `timeout_seconds`, or returns a line beginning `WORKFLOW_ESCALATE:`. A successful child without that marker is complete. The runner asks children to use the marker rather than bluff when they are stuck or cannot complete reliably.

Adaptive verification is opt-in with `verifies`; do not attach a verifier to every cheap task. A verifier that finds a material correctness or acceptance failure ends its final response with `WORKFLOW_REJECT: <task-id>: <evidence>`. The runner reads only a trailing marker block, escalates and reruns only that task, records the feedback in its state, and then reruns the same verifier. Direct consumers must also depend on the verifier so stale output cannot escape before acceptance. If the rejected task reaches its tier or attempt bound, the workflow fails closed instead of spending more tokens on unrelated work.

Prompt placeholders:

- `{{run_dir}}` → this run's state directory.
- `{{output:<task-id>}}` → the dependency's output text, with path and truncation notice when needed.
- `{{var:NAME}}` → a reusable non-secret input supplied with `--var NAME=value`. Variables are persisted in run state for resume; credentials belong in Hermes provider/tool configuration, not workflow variables.

## Workflow

### 1. Decide whether to use it

Use this runner when at least one is true:

- the task has many genuinely independent units;
- intermediate output would materially crowd the parent context;
- the same orchestration should be inspected or rerun;
- separate verifier/refuter stages improve trust;
- isolated worktrees are useful for parallel code changes.

Use normal Hermes execution or one `delegate_task` batch for small bounded work. A fixed serial procedure with no LLM judgment should be a normal script, not a multi-agent workflow.

### 2. Build the smallest plan

1. Inspect the target and identify independent units and real dependencies.
2. Put deterministic discovery in one task or perform it before the plan.
3. Fan out only irreducible judgment/work.
4. Add adaptive verification only when independent checking is cheaper than starting the producer stronger; otherwise start at the stronger tier and skip the extra agent.
5. Start with `max_workers: 2-4`. Do not silently create dozens of full agents.
6. For code changes, assign non-overlapping scopes and use `worktree: true` only when each result is independently integrable.
7. Set `automatic_routing: true`; for each task classify only the minimum intelligence tier, whether latency blocks the user, and failure cost. Do not choose a model or generate a receipt manually. The runner owns selection and pinning.

For consequential write workflows, derive objectively verifiable acceptance items, ground paths/symbols/commands before launch, assign every item to a task, and pass all items to the final verifier. When a cross-layer design remains unproven, run one thin end-to-end tracer before parallel expansion.

Choose review depth deliberately. Balanced review uses one independent reviewer with separate specification and quality verdicts. Strict review uses separate specification and quality nodes only when requested or justified by failure cost. Encode correction rounds in the DAG, cap them at three, and stop earlier if material findings do not decrease.

Prefer a few coherent shards over one task per tiny file. Parallelism is useful only when units do not fight over shared state.

### 3. Validate and preview

```bash
python <skill-dir>/scripts/workflow_runner.py validate <plan.json>
python <skill-dir>/scripts/workflow_runner.py preview <plan.json>
```

Before launching, state the task count, maximum concurrency, side-effect surface, and whether worktrees/remote writes are involved. Explicit workflow/ultracode invocation is enough approval for a bounded read-only run. Use `clarify` before launching if the generated plan materially expands scope, uses more than 8 agents, deploys/publishes/pushes, or performs broad writes the user did not already request.

### 4. Run in the background

```bash
python <skill-dir>/scripts/workflow_runner.py run <plan.json>
```

For saved templates with inputs:

```bash
python <skill-dir>/scripts/workflow_runner.py run <plan.json> --var QUESTION="What changed?"
```

Use `terminal(background=true, notify_on_complete=true)` for a bounded run so the chat remains usable and completion is reported. Do not wrap it in `nohup`, `start`, or an untracked shell background process.

Each task runs as a temporary child process. The runner captures its output, waits for process termination, and reaps the process handle before marking the task complete. When invoked from a Hermes session, it also strips inherited controller identity, registers the child through the runtime's opaque ephemeral-session receipt, and acknowledges cleanup only after the task output file is durably copied; failed, interrupted, ambiguous, adopted, or referenced sessions are retained. Stop requests terminate the process tree and confirm exit before persisting `stopped`; completed workers must never remain running.

### 5. Inspect and resume

```bash
python <skill-dir>/scripts/workflow_runner.py list
python <skill-dir>/scripts/workflow_runner.py status <run-dir-or-id>
python <skill-dir>/scripts/workflow_runner.py stop <run-dir-or-id>
python <skill-dir>/scripts/workflow_runner.py resume <run-dir-or-id> --retry-failed
```

A resume preserves successful outputs and retries only failed/interrupted work when requested. It does not make an in-flight process restart-proof across machine reboots.

### 6. Verify the result

- Read `state.json`; do not trust a child summary alone.
- Confirm the pinned `model_policy`, reasoning effort, tier bounds, and each task's `attempt_history` match the intended route and escalation.
- For adaptive tasks, inspect `feedback_history` and confirm rejected outputs were rerun before gated consumers launched.
- Confirm every required task is `succeeded` and every output file exists.
- Inspect the final synthesis output and relevant evidence files.
- For code-changing tasks, independently inspect each worktree/diff and run integration tests in the combined target before claiming success.
- Report failed or blocked tasks directly; do not fabricate a unified result from missing shards.

## Reusable recipes

- `templates/deep-research.template.json`: independent source angles → claim verifier → cited synthesis.
- `templates/code-audit.template.json`: discovery → two differently framed audits → adversarial verifier → ranked report.
- `templates/migration.template.json`: plan → isolated implementation shards → review/synthesis. Adapt scopes before running.
- `references/runtime-contract.md`: load when changing/reviewing the runner or comparing the compatibility layer with a native runtime; it contains the safety, durability, and verification contract.

## Pitfalls

- More agents are not automatically better. Cost and correlated mistakes scale too.
- Escalation detects concrete failure, timeout, explicit inability, or an opt-in verifier rejection. It still cannot infer wrong output without a checkable acceptance contract.
- Weak-first plus a verifier can cost more than starting stronger. Route per task; use `verifies` only when the expected checking value justifies another model call.
- A task in `include_outputs` must be a dependency; otherwise the plan is nondeterministic.
- Generated prompts and outputs can be large. The runner caps injected output; tasks also receive the full output path.
- `worktree: true` isolates files but does not merge branches. The parent still owns integration.
- The workflow runner deliberately passes prompts as argv without `shell=True`; do not replace this with shell interpolation.
- Do not edit Hermes source to register commands. This custom skill already appears as `/cc-dynamic-workflows` after a skill reload/new session.
