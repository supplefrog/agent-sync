# OMP V3 workflow adapter

OMP uses the portable state CLI and its native task-agent mechanism. The existing `install_omp_route_agents.py` owner remains V2-only and rejects V3 catalogs before changing agent files.

For each dependency-ready V3 task, build explicit `execution_context` JSON from the actual OMP controller and call `dispatch` once.

- `parent` or `deterministic`: return the action to the parent. After the parent actually performs and checks the work, run `claim-parent`, `start` with `parent-sequential:<task-id>`, and `finish` with the same token and real output.
- `defer`: leave the task pending and visible. Do not launch a generic agent or spin the ready loop.
- `model`: fail closed unless the receipt selects an admitted `omp-workflow` catalog cell and `route-<route-id>` exists with the exact `openai-codex/<model>` and `thinkingLevel`. Then claim, dispatch that named agent with the frozen prompt, attach its native handle, verify `resolvedModel`, persist the full output, release the handle, and finish with the exact token and `--handle-closed`.

The current admitted V3 catalog contains no OMP cell, and no V3 OMP agent generator has been admitted. A synthetic state-machine test does not authorize native dispatch or agent installation. Lifecycle success leaves independent acceptance to the parent.
