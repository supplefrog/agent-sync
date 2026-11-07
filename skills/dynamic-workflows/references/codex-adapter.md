# Codex V3 workflow adapter

Codex uses the portable state CLI plus native workers; there is no second executable adapter.

For each dependency-ready V3 task, build explicit `execution_context` JSON from the actual controller state, including inherited context or profile identity supplied separately from the task prompt. Call `dispatch` once with that JSON.

- `parent` or `deterministic`: show the returned action to the parent. After the parent actually performs and checks the work, run `claim-parent`, then `start` with the exact `parent-sequential:<task-id>` handle, and `finish` with the matching token and real output path.
- `defer`: leave the task pending and visible. Do not claim it or repeatedly call `ready` to manufacture progress.
- `model`: proceed only when the receipt selects a current admitted `codex-workflow` cell and the controller can verify worker release. Read `model`, render the frozen prompt, claim, spawn a fresh-context native worker with the exact provider, model and effort, and attach its native handle with `start`. Keep child delegation disabled. Persist the full output, verify release, then call `finish --handle-closed` with the same handle and token.

## Route and resource scope

`codex-gpt61-sol-medium-workflow` selects the native ChatGPT subscription route for GPT-6.1 Sol at medium effort. The catalog limits this cell to tasks with no required tools or effects. For a bounded, low-risk task, provide an independent complete verifier, one attempt, a current `codex-main` quota observation in percentage points, and an explicit route preference when cost is unknown. Check the exact callability evidence and its validity window before a new dispatch. Refresh expired evidence with a new native observation and retain old pins. Reject mismatched provider, model or effort. Verify the effective child settings using native session metadata where available.

## Verify worker release

- When the host exposes native `close_agent`, wait for the result, persist it and explicitly close that handle. Use the native close result as the release witness.
- When the host exposes only collaboration spawn, wait and interrupt, use a dedicated, non-resumed `codex exec` controller for the routed node. Start it in the authorized workspace with the normal sandbox and approvals and capture its native events. Bind the actual controller identity in `dispatch`. The controller claims and starts the worker, waits for its native terminal status and saves the full result. Keep the run open at this point. The calling parent verifies that the native child belongs to that controller, reached a terminal state, and that the dedicated controller process exited cleanly. Its exit releases the controller-owned worker handle. Then the calling parent finishes the node with the saved handle and claim token. A completed child listed in a still-running controller is insufficient evidence of release.
- If either release path is unavailable or the native evidence is incomplete, keep the node unresolved and reconcile its handle before attempting further work.

The parent independently verifies the result against the task's declared acceptance after the lifecycle check. A lifecycle receipt alone does not establish task quality.
