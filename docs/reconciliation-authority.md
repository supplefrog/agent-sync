# Reconciliation authority and conflict protocol

## Authority invariant

Hermes Kanban is the sole authority for task existence, identity, scope, ownership, status, priority, dependencies, and completion. A canonical task claim is the current task record on its named Kanban board, interpreted with that board's dependency graph and event history.

Hermes sessions, Codex sessions, OMP sessions, and manual-agent logs are evidence containers only. They may supply requests, execution evidence, or discrepancy reports. They must never directly create, reopen, reassign, reprioritize, merge, split, block, or complete a task. A change becomes authoritative only after it is recorded through a supported Hermes Kanban operation and read back from the board. The reconciliation ledger, monitor queue, reports, receipts, inferred goals, and thread-local plans are not task authorities.

## Claim classes

Every observed statement must be classified before comparison:

- `board-claim`: current Kanban task fields, dependency edges, and lifecycle events;
- `user-evidence`: an explicit user statement in a native source;
- `execution-evidence`: a source-linked artifact, test result, receipt, or terminal event;
- `agent-claim`: an assistant or worker assertion without independent verification;
- `inference`: a proposed relationship or broader goal not stated by a source.

Source identity and claim class are separate. Copying a claim between systems does not strengthen it or make the copies independent.

## Conflict priority and resolution

Apply this order to every conflict:

1. **Current Kanban state wins operationally.** Read the named board's current task row, dependency edges, and latest lifecycle events. Use that state for dispatch, ownership, status, and completion regardless of any external claim.
2. **A read-back Kanban mutation supersedes older Kanban state.** When an authorized reconciliation decision changes the board, read the resulting task and use the read-back state. A requested, attempted, or reported mutation without read-back does not count.
3. **Explicit user evidence proposes a board correction but cannot bypass the board.** Preserve the source locator and surface the discrepancy for an authorized Kanban mutation. Until that mutation succeeds and is read back, the existing board state remains effective.
4. **Verified execution evidence may substantiate a correction.** Prefer evidence bound to the exact task, artifact, revision, and acceptance check over unbound or stale evidence. It can justify a proposed status change but cannot change status itself.
5. **Agent claims are non-authoritative.** Use them only as leads to inspect their cited source or artifact. An uncited completion, ownership, or scope assertion never resolves a conflict.
6. **Unsupported inference loses to every sourced claim.** Do not write it as fact or use it to mutate the board.

Hermes, Codex, OMP, and manual-agent systems have equal rank when they contain the same claim class. There is no hidden source-system tie-breaker among them. For evidence at the same rank, prefer evidence that is directly bound to the task and acceptance check, then the later native source event. If equally ranked evidence still conflicts, or if identity, lineage, timestamps, or authority to mutate is ambiguous, preserve both claims, mark the discrepancy unresolved, and require manual review. Never resolve ambiguity by majority vote, assistant confidence, source prestige, or last-write-wins across clocks.

A conflict is resolved only when the reconciliation record contains:

- the affected Kanban board and task ID;
- all conflicting source locators and observed timestamps;
- the priority rule applied;
- the resulting Kanban state or the reason no mutation was allowed; and
- read-back evidence for any Kanban mutation.

## Broader-goal inference gate

A broader goal may be proposed only when all of these conditions hold, with no exceptions:

1. At least two independent source systems contain explicit, source-linked evidence for the same broader outcome. Eligible systems are Hermes session history, Codex session history, OMP session history, manual-agent logs, and Hermes Kanban.
2. Each source independently states enough of the goal to identify the same intended outcome and material scope. Shared keywords, topical similarity, temporal proximity, or one system quoting another are insufficient.
3. The evidence items have independent provenance. Mirrored messages, imports, forks, summaries, copied prompts, and agent restatements derived from one origin count as one source.
4. No authoritative Kanban field or explicit user evidence contradicts the proposed goal, scope, or relationship.
5. The inference record cites both source systems and locators, states the proposed goal, lists the linked Kanban task IDs, and explains the independent support without adding unsupported scope.

Failure of any condition means `insufficient-evidence`: keep tasks separate and do not infer the goal. Two agreeing agent assertions without explicit underlying evidence do not pass. A passing inference is still evidence only; it becomes an actionable goal or relationship only after a corresponding Kanban task or dependency change is authorized, written, and read back.

## Mid-reconciliation arrivals

Each reconciliation run operates on a bounded source snapshot and records a start watermark for every source plus every Kanban board discovered at start.

1. Reconcile only records at or before the start watermarks.
2. Before emitting a final result or applying any proposed mutation, rescan all sources and discover Kanban boards again.
3. If Kanban changed, a board appeared, or a task was created or changed after the watermark, stop finalization, mark the run `stale-authority`, preserve its partial evidence, and start a new reconciliation cycle from fresh watermarks. Do not apply conclusions computed against stale board state.
4. If only a non-Kanban session or log changed, quarantine the delta as `arrived-during-run`, surface it for review, and process it in the next cycle. It must not silently alter the current snapshot's conclusions.
5. If a new external claim has no Kanban task, record it as `unmapped-evidence` for manual review. Do not create a shadow task in the monitor, ledger, report, session, or thread plan. An authorized operator may create a Kanban task; only its read-back establishes the task.
6. Repeat the rescan until one cycle reaches finalization with no authority-changing Kanban delta. Continuous arrivals may delay closure; they never justify ignoring new board state.

Retries use the same event identity and preserve prior discrepancy records. Processing is idempotent: the same evidence must not create duplicate Kanban tasks or repeat a mutation whose read-back already matches the intended state.

## Fail-closed conditions

Do not infer, mutate, or declare reconciliation complete when the Kanban board is unavailable, a board identity is ambiguous, source provenance is missing, a claimed mutation cannot be read back, independent-source evidence cannot be established, or a mid-run Kanban delta remains unprocessed. Surface the condition for manual review and retain the last verified Kanban state as authoritative.