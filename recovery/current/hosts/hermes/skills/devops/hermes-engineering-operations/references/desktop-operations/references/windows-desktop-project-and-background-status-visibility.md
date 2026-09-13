# Desktop project and background-status visibility

Use for reports where a chat seems to move, stop, or lose its workers after a project switch or after the parent turn finishes.

## Separate the layers

- **Project membership** changes the chat's workspace, sidebar grouping, and branch display; it does not inherently fork or stop the session.
- **Native subagents** may appear in the transient Subagents/status UI.
- **Durable workflow/background processes** can remain healthy while not appearing as native subagent cards.
- **Chat task boards** are reconciled summaries, not necessarily live projections of every runner transition.
- **Runner/process state** is authoritative for whether durable work is still active.

## Diagnostic sequence

1. Identify the durable session and active Project before and after the apparent move.
2. Check the relevant runner/process state directly; do not infer liveness from collapsed Desktop chrome.
3. If a workflow runner exists, read its persisted status and report task counts by `succeeded`, `running`, `pending`, and `failed`.
4. Confirm whether project switching changed only workspace/sidebar association or also changed files/session identity.
5. Audit repository diffs separately from session-to-project associations. A misplaced conversation does not prove files were written to the wrong repository.
6. Preserve history while correcting associations; never delete or re-home sessions broadly from UI appearance alone.

## User-facing contract

Treat the parent conversation as the control thread unless the user explicitly designates another. Tell the user where status should be requested. When long work continues after the turn, name the run and give a compact live summary. Completion must return to the control thread.

## Upstream classification

- Running work becomes undiscoverable after transient task/subagent UI collapses: status visibility / persistent session drawer.
- A new message wipes still-running native subagent rows: subagent lifecycle projection.
- Completed work stays `running` or results appear only after another message: terminal-state reconciliation.
- Project selector disappears or current workspace is unclear: project/sidebar navigation.

Search existing upstream issues for the exact symptom before filing. Add current-version evidence to the closest live owner rather than creating a broad duplicate.