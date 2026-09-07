# Codex V3 workflow adapter

Codex uses the portable state CLI plus native workers; there is no second executable adapter.

For each dependency-ready V3 task, build explicit `execution_context` JSON from the actual controller state, including inherited context or profile identity supplied separately from the task prompt. Call `dispatch` once with that JSON.

- `parent` or `deterministic`: show the returned action to the parent. After the parent actually performs and checks the work, run `claim-parent`, then `start` with the exact `parent-sequential:<task-id>` handle, and `finish` with the matching token and real output path.
- `defer`: leave the task pending and visible. Do not claim it or repeatedly call `ready` to manufacture progress.
- `model`: proceed only when the receipt selects an admitted `codex-workflow` cell. Read `model`, render the frozen prompt, claim, spawn one native worker with the exact provider/model/effort and child delegation disabled, attach its native handle with `start`, persist its output, close the handle, and call `finish --handle-closed` with the exact token.

The current admitted V3 catalog contains only a Hermes direct cell, so Codex V3 presently resolves to parent, deterministic, or defer. A synthetic test catalog proves the portable model branch only; it is not Codex route admission. Lifecycle success preserves the pending independent acceptance handoff and does not prove result quality.
