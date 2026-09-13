# Delegated Kanban audit handoff

Use this when a read-only repository audit is running inside a delegated Kanban worker and the parent expects a terminal board transition.

## Safe preflight

1. Treat board mutation as a separate operation from repository verification.
2. Inspect supported syntax without mutating the board:
   - `hermes kanban --help`
   - `hermes kanban complete --help`
   - `hermes kanban block --help`
3. If useful, make one read-only task inspection attempt (`hermes kanban show <task-id>`), but a child-context guard may reject even database initialization.

## Terminal handoff

- If the child context is authorized and the audit is complete, use the supported CLI once:
  `hermes kanban complete <task-id> --summary '<verified handoff>' --metadata '{"artifacts":[...],"verdict":"PASS"}'`
- If the audit is genuinely blocked and the child context is authorized, use one supported block operation with a typed reason.
- If the command reports a delegated-child mutation guard, stop. Do not retry alternate syntax, direct SQLite writes, equivalent persistence calls, or repeated complete/block attempts. Return the exact refusal, verified evidence, artifact paths, and state that the parent/orchestrator must close the task.

A plain review result is still the correct repository deliverable when board closure is prohibited by the child-context guard; the refusal is an operational handoff blocker, not a repository finding.