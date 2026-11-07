# Codex V3 workflow adapter

Codex uses the portable state CLI and native workers. The Codex availability helper qualifies routes before dispatch and leaves scheduling and lifecycle state with the portable CLI.

For each dependency-ready V3 task, build explicit `execution_context` JSON from the actual controller state, including inherited context or profile identity supplied separately from the task prompt. Ordinary dispatch verifies the on-demand route automatically for an unbound task that prefers it.

- `parent` or `deterministic`: show the returned action to the parent. After the parent actually performs and checks the work, run `claim-parent`, then `start` with the exact `parent-sequential:<task-id>` handle, and `finish` with the matching token and real output path.
- `defer`: leave the task pending and visible. Do not claim it or repeatedly call `ready` to manufacture progress.
- `model`: proceed only when the receipt selects a current admitted `codex-workflow` cell and the controller can verify worker release. Read `model`, render the frozen prompt, claim, spawn a fresh-context native worker with the exact provider, model and effort, and attach its native handle with `start`. Keep child delegation disabled. Persist the full output, verify release, then call `finish --handle-closed` with the same handle and token.

## Route and resource scope

Start with the V3 plan template. Set the exact `requirements.model`, `requirements.reasoning_effort` and tool names. For eligible Codex subagents, default to `unknown_cost_policy: explicit_preference` and `preference_order: ["codex-workflow-on-demand"]`. Honor an explicit alternative route or parent policy. The account and runtime must support the exact requested tuple. Each different model or effort requires its own native proof.

The route accepts bounded, low-risk tasks with one attempt, no fallback, and an independent deterministic verifier with complete coverage. Tool tasks require `artifact-effects` verification. The native probes cover local `exec_command`, `shell_command`, `functions.exec` wrapping shell commands, and `apply_patch`. Use `none` for read-only effects or `reversible` for authorized local edits. Patch requires reversible effects. Include the current positive `codex-main` subscription quota in percentage points with zero reserve. The on-demand command may spend one additional native probe when proof is missing or stale.

```text
python scripts/workflow_state.py dispatch <run-dir> <task-id> --execution-context <json>
```

The command reuses proof for 24 hours only when the exact tuple, tool scope, native profile, and controller execution context match and the native evidence still verifies. Otherwise it runs one scratch probe using the native ChatGPT subscription, with apps, web search and approval requests disabled. An unsupported tool, mismatched route or failed probe leaves the task unbound with a reason. Keep the cache and run state under the controller's ownership. The task's catalog and receipt freeze at first dispatch, so an unbound dependent node can refresh without changing an earlier node's receipt. The previously published fixed Codex cell remains available through ordinary catalog dispatch while its evidence is current.

Verify the actual worker's native provider, model, effort, authorized tools and effects. Apply the workload's normal sandbox and approvals independently of the scratch probe.

## Verify worker release

- When the host exposes native `close_agent`, wait for the result, persist it and explicitly close that handle. Use the native close result as the release witness.
- When the host exposes only collaboration spawn, wait and interrupt, use a dedicated, non-resumed `codex exec` controller for the routed node. Start it in the authorized workspace with the normal sandbox and approvals and capture its native events. Bind the actual controller identity in `dispatch`. The controller claims and starts the worker, waits for its native terminal status and saves the full result. Keep the run open at this point. The calling parent verifies that the native child belongs to that controller, reached a terminal state, and that the dedicated controller process exited cleanly. Its exit releases the controller-owned worker handle. Then the calling parent finishes the node with the saved handle and claim token. A completed child listed in a still-running controller is insufficient evidence of release.
- If either release path is unavailable or the native evidence is incomplete, keep the node unresolved and reconcile its handle before attempting further work.

The parent independently verifies the result against the task's declared acceptance after the lifecycle check. A lifecycle receipt alone does not establish task quality.
