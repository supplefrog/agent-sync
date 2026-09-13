# Session Lifecycle Cleanup Audit

Reusable evidence and design notes for cleaning up agent-spawned Hermes sessions without deleting user-owned or shared conversations.

## Local DAG runner findings

Audited `{{agent-signal:HERMES_HOME}}/skills/autonomous-ai-agents/cc-dynamic-workflows/scripts/workflow_runner.py` and `tier_chat.py`.

- `workflow_runner.py:822-852` builds each child as `hermes chat ... --quiet --source tool ...`; the command has no child session ID, parent session ID, or lifecycle token.
- `workflow_runner.py:431-469` persists run/task state, model routing, output paths, PIDs, and attempts, but no Hermes child session identity.
- `workflow_runner.py:1213-1275` records subprocess PIDs and attempt files only.
- `workflow_runner.py:1163-1200` and `1295-1305` stop/reap child OS processes. This is process cleanup, not session-row cleanup.
- `tier_chat.py:30-43` changes reasoning effort in-process and invokes the normal CLI; it does not add lifecycle identity.
- `run_agent.py:93-103` derives the session source from `HERMES_SESSION_SOURCE`; `run_agent.py:628-666` creates the row using that source. `agent/agent_init.py:1511-1519` generates a new session ID when none is supplied.

Therefore, `source='tool'` is only a broad classification. It cannot prove that a row was created by this workflow, identify its parent, or establish that deletion is safe. The typed launch contract must return both the child session ID and an opaque runtime-issued ownership handle. Persist both in workflow state: the session ID is a locator, while the ownership handle plus current adoption/protection state is deletion authority. Never infer either from output, cwd, timestamps, titles, parent links, or source.

## Stronger existing patterns

- Internal delegation passes `parent_session_id` and writes `_delegate_from`: `tools/delegate_tool.py:1640-1642`, `1673-1679`.
- Session deletion cascades only explicitly marked delegate children and preserves untagged children: `hermes_state.py:287-309`, `9526-9583`.
- `SubagentLifecycleService` provides signed handles, parent IDs, correlation IDs, terminal states, and bounded retention: `agent/subagent_lifecycle.py:242-259`, `389-407`. It is an in-process lifecycle registry, not durable session deletion.
- Durable async delegation records owner PID and process-start identity, recovers abandoned owners, and has explicit completion delivery states: `tools/async_delegation.py:147-183`, `335-389`, `526-560`.
- TUI teardown distinguishes gateway-owned sessions from TUI-owned sessions and interrupts only owned background work: `tui_gateway/server.py:637-659`, `733-787`.
- The narrow empty-session deletion primitive is transactional and requires no messages, no user title, and no children: `hermes_state.py:9585-9627`.

## Recommended ownership contract

One core runtime/spawner-owned registry should serve `delegate_task`, public lifecycle APIs, and durable workflow runners. Skills and workflow definitions should not implement competing cleanup policies.

At spawn, persist an opaque `spawn_id`, parent session ID, child session ID, owner kind, owner PID plus process-start token, `ephemeral=true`, terminal state, integration state, and protection/adoption state. Keep `source='tool'` for filtering, but never use it as deletion authority.

Delete only after all of these are true:

1. The ownership token still matches.
2. The child is terminal.
3. Its useful result has an explicit integration acknowledgement.
4. No active process, turn, lease, async delegation, or descendant work remains.
5. No user adoption, title, resume, message, export, pin, sharing, or protected reference exists.
6. A final transaction rechecks the candidate set and ownership before deleting transcript files and rows.

If any condition is uncertain, retain the session. On crash/restart, mark ownership abandoned or unknown first; never infer that an unobserved child is safe to delete. A user interaction adopts the session as durable.

## Pre-removal evidence audit

Before archiving or deleting an unexplained task, synthetic card, caretaker card, or its worker session, inspect the primary records—not only a caretaker summary:

1. Read the full task specification, creator/provenance, current state, block reason, result, and acceptance contract.
2. Read every run/event outcome needed to reconstruct what actually executed, including claims, replacement/reclaim events, timeouts, active leases, and worker identity.
3. Inspect comments, parent/child links, attachments, delivered artifacts, workspace contents, task log, and the exact worker transcript when one exists.
4. Distinguish an empty synthetic test artifact from abandoned legitimate work or user-owned work. A vague title is not enough evidence either way.
5. Preserve the audit evidence and any useful output before mutation. Archive the task when the audit trail is valuable; hard-delete only when supported ownership rules authorize it.
6. After archival, delete an agent-created temporary worker session only when its useful output is integrated elsewhere and the ownership/adoption checks above pass. Verify both task and session readback.

If removal happened before this audit, say so plainly, perform the audit immediately, and restore or retain anything useful. Never claim “nothing was lost” until primary task, workspace, log, and session evidence support it.

## OMP saved-session cleanup

Use current OMP session documentation before acting; storage and lifecycle behavior are host-owned and may change. For a bounded manual cleanup:

1. Inventory top-level saved-session JSONL files separately from nested task-agent transcripts. A top-level transcript's same-stem directory is its artifact bundle and may contain child JSONL transcripts, agent outputs, tool logs, and `local://` evidence. Enumerate that bundle before treating one visible parent as one removable file.
2. Establish semantic terminality from the parent goal, final outcome, current todo state, child `yield`/delivery evidence, and any explicit replacement or rebinding. A failed child is removable as superseded only when later evidence proves its assignment was completed elsewhere; failure alone does not close the work.
3. Present the cleanup plan by topic: what each parent and child was about, what completed it, what was superseded, and which artifacts disappear. Count logical threads separately from physical paths. Obtain scoped approval after this explanation, not after an ID-only inventory.
4. Check both runtime activity and saved pointers. OMP's `terminal-sessions` breadcrumbs can make garbage collection report a session as active even when no OMP process exists. Inspect the referenced path and live process independently; remove only breadcrumbs that are stale or explicitly covered by the approved session deletion.
5. Prefer the native session selector's confirmed deletion for ordinary interactive cleanup; it removes the selected JSONL and its artifacts. `/drop` is best-effort for the current session and starts a new one. `omp gc --archive` is useful as a default-dry-run diagnostic but archives cold sessions rather than performing exact per-session deletion.
6. For exact offline cleanup, delete only the approved top-level JSONL, its same-stem artifact directory, and in-scope stale breadcrumbs after proving no process, turn, lease, or managed worktree remains. Do not create an export when the user explicitly declined retention.
7. Verify by re-enumerating targeted transcripts, artifact bundles, and breadcrumbs; rerun the OMP dry-run/listing checks and confirm no targeted worktree or process remains. Report logical sessions removed, ancillary artifacts removed, and any retained uncertainty separately.

## Nested Hermes CLI isolation

A Hermes CLI child launched from a Kanban or delegated worker must not inherit the parent controller identity. Before `Popen`, remove every `HERMES_KANBAN_*` key, `HERMES_DELEGATED_CHILD_CONTEXT`, inherited Hermes session/gateway identity (`HERMES_SESSION_ID`, parent/key/source/gateway variants), and delegation-control prefixes. Otherwise an evaluation or workflow child can execute the parent worker lifecycle instead of its prompt.

For tightly scoped direct children:

1. Capture the runtime-issued session ID from that exact child process; require exactly one valid receipt and fail closed on missing or ambiguous receipts.
2. Treat session listing, source, title, cwd, and timestamps as readback only—not identity discovery or deletion authority.
3. Preserve output durably before cleanup. On failure, timeout, or interruption, terminate/reap the child, capture any exact receipt, and retain evidence needed to explain the outcome.
4. Protect the parent explicitly, provide a retain-evidence override, use supported session controls, and verify zero remaining owned children by readback.
5. Migrate the adapter to the central opaque ownership-token contract when available; the direct receipt is a locator bound to one spawning process, not a substitute for global lifecycle governance.

## Minimal host adapters

1. `delegate_tool` / `SubagentLifecycleService`: register spawn, propagate identity, and expose the child session ID/token.
2. DAG runner: use a typed internal CLI/API launch contract, record the returned child session ID in `state.json`, and emit an integration acknowledgement. Do not infer identity from `source=tool`.
3. Parent delivery/final synthesis: call the central registry's integration hook. The registry performs the guarded cleanup.

Prefer an internal argv/API contract over a new user-facing environment variable for non-secret lifecycle metadata.

## Primary references

- Sessions and source tagging: https://hermes-agent.nousresearch.com/docs/user-guide/sessions
- CLI `--source` reference: https://hermes-agent.nousresearch.com/docs/reference/cli-commands
- Session storage and lineage: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/session-storage.md
- Public subagent lifecycle: https://raw.githubusercontent.com/NousResearch/hermes-agent/main/agent/subagent_lifecycle.py
- Durable async delegation: https://raw.githubusercontent.com/NousResearch/hermes-agent/main/tools/async_delegation.py
- Session DB deletion: https://raw.githubusercontent.com/NousResearch/hermes-agent/main/hermes_state.py
- TUI ownership guard: https://raw.githubusercontent.com/NousResearch/hermes-agent/main/tui_gateway/server.py
