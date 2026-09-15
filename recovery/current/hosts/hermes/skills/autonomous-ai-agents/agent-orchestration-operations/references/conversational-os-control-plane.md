# Conversational OS control plane

Use when the desired product is one conversational surface that internally owns multiple tasks, rather than a user-facing board or thread manager.

## User-visible contract

- Any conversation can accept a new goal, a correction, or `status` without requiring the user to identify a card, thread, mode, or worker.
- The system detects task boundaries, reconciles new text against existing work, and internally creates, deduplicates, links, pauses, resumes, or retires execution contexts.
- Brainstorming, research, decision, execution, independent verification, and follow-up remain one interactive relationship even when work fans out internally.
- The composer can show and steer several tasks inline. Status reconciles all material work and distinguishes truly running, queued, waiting, blocked, and done states.
- User wording, evolving intent, decisions, rejected alternatives, evidence, and task lineage survive compaction, restart, and conversation changes.
- Only a decision that changes the correct action interrupts the user. Internal cards, retries, review states, worker identities, and framework vocabulary stay implementation detail unless requested.

## Cross-session recovery

When the user references earlier work or assumes the orchestrator should know it:

1. Start with an explicitly supplied task index and linked artifacts. If evidence is missing and history retrieval is permitted, search session history using distinctive outcome, framework, artifact, and decision terms; never use it to fill gaps during an artifact-only continuity check.
2. Inspect the original source named in or recovered from history—repository artifacts, documents, issue/thread, live board, or external system—before relying on summaries.
3. Recover the goal, final decisions, rejected alternatives, evidence handles, and unresolved questions. Distinguish kickoff from resolution using artifact checkpoints; when history retrieval is permitted and used, inspect session bookends and nearby messages as well.
4. Reconcile recovered work with current reality. Do not rebuild an inventory or architecture that already exists.
5. If a foundational assumption changed, preserve the evidence but reopen dependent conclusions. State explicitly which old invariant made the prior result provisional.

A chat summary, memory entry, dashboard, or Kanban card is a view, not sufficient proof of the current source or complete decision lineage.

## Internal authority

Do not hard-code Kanban, a chat transcript, or another incumbent store as the permanent authority while substrate selection is open. Name the current temporary authority and migration boundary. The selected conversational OS must own a durable intent/event model from which task views, status, threads, workers, and UI projections derive.

Boards may remain useful as an operator/debug projection. They must not require user management and must not constrain replacement candidates by assumption.

## Execution container in current Hermes

For work that must continue across turns in one session, verify the current official Hermes docs and use the documented in-session `/goal` command when available. Do not infer that goals are absent merely because no top-level `hermes goal` CLI subcommand exists. A goal is a temporary continuity mechanism, not the final conversational-OS architecture.

## Snapshot side questions

1. Inspect the installed command registry and matching native handler before designing a side-chat workaround. In Hermes Desktop, check `/btw` in `desktop-slash-commands.ts`, `prompt.btw` in `tui_gateway/methods_prompt.py`, and `agent/side_question.py`; discover current locations rather than assuming an old checkout path.
2. Trace snapshot capture, tool-dispatch restrictions, persistence detachment and the `btw.complete` UI handler. Distinguish a visible answer from an addition to the main model's message history. Source inspection establishes intended behavior, not successful live delivery or restart isolation.
3. Use `/btw` for questions such as “explain the last known task list.” Disclose snapshot freshness; the inspected tool-free implementation cannot reread an index or query live workers. Keep fresh-status retrieval on an existing authoritative read-only view or the coordinator path.
4. Validate the actual Desktop behavior under normal inference authorization before declaring the feature working. Do not create duplicate persistent sessions just to test a snapshot question, or change auxiliary routing as an incidental convenience.
5. Only propose a local extension when a verified gap remains. Bind it to a reproducer, exact local patch, rollback and retirement test; do not turn snapshot Q&A into autonomous task mutation or a competing task store.

## Bounded completion-to-next-task inspection

Use when dispatch works but automatic coordinator progression remains uncertain.

1. Recover the authorized outcome and current checkpoint from the selected task source. Apply explicit supersession notes before interpreting older pending entries. Identify the actual execution shape: native child, existing-thread continuation, invoked DAG or subscribed durable task; each can have a different completion consumer.
2. Trace the submitted call to its definition and arguments, then follow terminal-event production → origin/turn binding → queue or callback → ownership/claim checks → coordinator turn → evidence reconciliation → next-task selection. Use targeted `search_files` queries and batched `read_file` ranges. Inspect both producer and consumer: a consumer's existence does not prove this producer feeds it, and caller identity retained for admission does not prove a terminal return address.
3. Compare neighboring native mechanisms only to locate a reusable seam. Distinguish an invoked DAG advancing ready nodes from an idle coordinator receiving an external completion. Distinguish synchronous fallback from deferred delivery. Do not create a board, change routes or add a scheduler merely to make the inspection fit an available mechanism.
4. Separate observed live receipts, inspected source/test definitions and unexecuted proposals. A submitted/queued receipt proves admission; a recipient acknowledgement proves delivery; neither proves return delivery, artifact acceptance or next-task dispatch. Do not report inspected tests as passed or turn a source-local absence into a permanent feature limitation.
5. Stop at the smallest missing edge. Name its existing owner and the next discriminating check rather than broadening into another audit. If testing is authorized, exercise the native seam with execution/dispatch doubles before live inference; cover success/failure, busy/closed/foreign ownership, duplicate or ambiguous delivery, and approval refusal/expiry. Plumbing fixtures do not establish live scheduling quality or confer permission to retry.
6. Write a concise handoff separating verified behavior, missing evidence and proposed change. Cite source ranges and fingerprint inspected files when the checkout is dirty, because its commit alone does not identify those bytes. Validate artifact links and report drift before handing off. Extend an existing instruction owner only for a demonstrated guidance gap; prose cannot supply a missing runtime event.

## Framework evaluation boundary

Before adapting Exo, Prime, LangGraph/Deep Agents, or another complete runtime into the incumbent, load `agent-capability-engineering` and use its whole-system substrate evaluation. Keep intact systems behind supported executor/RPC/ACP/MCP/CLI/sidecar boundaries during comparison. Select authority first; converge portable capabilities afterward.

## Regression signals

Treat each as a control-plane failure:

- the user has to remember or locate an existing inventory/task;
- `status` omits a material lane or calls queued work running;
- a correction attaches only to the current chat and not the owning task;
- the system recreates work because a summary omitted its artifact path;
- a framework is rejected because the incumbent was assumed canonical;
- the user must operate cards or threads to maintain task boundaries;
- a black-box success verdict hides missing steering, provenance, recovery, or interaction behavior.
