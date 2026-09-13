# Hermes-native reconciliation monitor safety

Use this reference when turning cross-thread intake into a Hermes cron + Kanban workflow.

## Safe architecture

- Keep Hermes Kanban as the only task authority. Session stores and provider histories are evidence sources.
- Use a deterministic metadata-only monitor before invoking an agent. Persist only provider-native IDs, event/cursor ranges, hashes, board slugs, task IDs, and source locators—not titles, prompts, messages, task bodies, or tool results.
- Baseline existing stores without queueing historical work. Subsequent scans emit only deltas.
- Scan all authoritative stores, including archived Codex sessions and every Hermes Kanban board DB, not only recent-session output or the selected board.
- Exclude reconciliation cron sessions from Hermes session deltas to prevent self-trigger loops. Continue observing Kanban mutations made by cron agents.
- Use stable event IDs and explicit completed receipts. A pending event remains pending and changes its attempt marker until a receipt matches schema version, event ID, completed status, and report path. This compensates for monitor systems that persist the output hash before the agent finishes.
- Reports contain distilled claims plus stable source handles. The agent reads changed evidence through native interfaces and verifies Kanban writes by readback.

## Kanban activation hazard

Do not assume `triage` means parked. Inspect the live Kanban dispatcher and config first. Hermes deployments may auto-decompose triage cards into child workgraphs and dispatch workers automatically.

Before populating a live orchestration board:

1. inspect `kanban.auto_decompose` and dispatcher behavior;
2. if automatic fan-out conflicts with the user's authority model, disable it through supported config and verify the live gateway re-reads the setting;
3. create durable bookkeeping cards in an explicitly non-dispatchable state such as `blocked`, not `triage`, unless decomposition is intended;
4. baseline monitor state before creating cards only when those card creations should be emitted as the first real delta;
5. run a production-seam test and verify no unexpected child cards, claims, or worker PIDs appear.

## Containment if fan-out starts

1. Pause the new cron job.
2. Engage Hermes's supported global pause so no new cron/Kanban work starts; understand that in-flight workers continue.
3. Read authoritative board state and collect only running cards created by the unintended decomposition.
4. Reclaim each running card through Kanban so its recorded worker is terminated and run history is closed.
5. Re-read task rows and process state; do not retry stale reclaim IDs blindly because workers may complete between checks.
6. Archive or delete only the contaminated agent-created board/cards after all workers are gone. Preserve user-created/shared boards.
7. Recreate intended cards in a non-dispatchable state, establish a fresh monitor baseline, validate one gateway tick, then lift the global pause.

## Verification

- unchanged monitor output suppresses the agent;
- changed metadata wakes exactly one receipt-gated reconciliation pass;
- a failed/missing receipt retries;
- monitor state/output contain no transcript or task payloads;
- new boards and tasks are detected without switching boards;
- cron sessions do not self-trigger;
- no unexpected Kanban worker remains after containment;
- unrelated cron jobs and boards remain unchanged.
