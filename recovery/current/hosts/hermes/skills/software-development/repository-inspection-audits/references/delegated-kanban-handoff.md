# Delegated Kanban audit handoff

Use only when an audit has an assigned board task. A missing task ID in an ordinary chat does not imply a broken board.

1. Inspect the assigned task with `kanban_show`; inspect any review/QA/release children before choosing the terminal action. Use native `kanban_*` tools, not the CLI or direct SQLite writes.
2. Finished assigned phase with a downstream review child => `kanban_complete(summary=..., metadata=...)` releases the child. Otherwise use `kanban_request_review` when same-card review is required; do not block for review.
3. Reviewer approval => `kanban_complete`; actionable rework => `kanban_request_changes`. Genuine missing input, access, dependency, or transient failure => typed `kanban_block`.
4. Deliverable files belong in top-level `artifacts` on completion, not only in metadata. State verification and board transition separately.
5. If the native tool is unavailable or rejects child authority, return the exact refusal, verified evidence and artifact paths to the parent. Do not try CLI syntax, direct persistence, or an equivalent mutation to bypass it. The parent owns the transition.

A board refusal is an operational handoff limit, not a repository defect. A read-only audit must not manufacture repository edits just to create a terminal receipt.
