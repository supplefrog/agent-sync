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

1. Search session history using distinctive outcome, framework, artifact, and decision terms.
2. Inspect the original source named in or recovered from history—repository artifacts, documents, issue/thread, live board, or external system—before relying on summaries.
3. Recover the goal, final decisions, rejected alternatives, evidence handles, and unresolved questions. Use session bookends and nearby messages to distinguish kickoff from resolution.
4. Reconcile recovered work with current reality. Do not rebuild an inventory or architecture that already exists.
5. If a foundational assumption changed, preserve the evidence but reopen dependent conclusions. State explicitly which old invariant made the prior result provisional.

A chat summary, memory entry, dashboard, or Kanban card is a view, not sufficient proof of the current source or complete decision lineage.

## Internal authority

Do not hard-code Kanban, a chat transcript, or another incumbent store as the permanent authority while substrate selection is open. Name the current temporary authority and migration boundary. The selected conversational OS must own a durable intent/event model from which task views, status, threads, workers, and UI projections derive.

Boards may remain useful as an operator/debug projection. They must not require user management and must not constrain replacement candidates by assumption.

## Execution container in current Hermes

For work that must continue across turns in one session, verify the current official Hermes docs and use the documented in-session `/goal` command when available. Do not infer that goals are absent merely because no top-level `hermes goal` CLI subcommand exists. A goal is a temporary continuity mechanism, not the final conversational-OS architecture.

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
