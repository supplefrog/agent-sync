# Event-driven Kanban caretaker lifecycle

Use this companion when implementing or reviewing automatic recovery for blocked/triage Kanban work. Kanban remains the sole task authority; the caretaker is a bounded worker, not a second scheduler or board.

## Runtime ownership

- Gateway dispatcher: normal readiness, dependency promotion, claims, provider-usage retry, stale-worker recovery after relaunch, and worker spawning. A provider quota sentinel returns the task to `ready` without increasing failure count and probes again on the native cooldown; do not create a caretaker for it.
- `kanban_task_blocked` hook: immediate signal for an actionable repeated-blocker episode.
- Script-only/no-agent cron: one-minute repair for hook events missed while relevant plugin processes were offline. It may rearm an event-current caretaker once after an operational `gave_up`; never retry an exact ambiguity or deliberate capability block as if it were transient.
- Native Kanban notification subscriptions: source cards in the active orchestrator chat are subscribed through the supported notification surface. Every new or existing caretaker inherits the source subscription. An exact caretaker ambiguity therefore becomes a native blocked-event notification in the originating Desktop/TUI chat; do not build a second messaging channel.
- Script-only operator recovery applies provenance-verified, event-current reversible actions through supported Kanban CLI commands and requires exact post-action readback. `specify` is valid only when the caretaker proves the correction no longer depends on user judgment; `archive` never purges. Ordinary `complete` remains parent-reviewed. Automatic completion requires `terminal_review`: successful caretaker-run metadata must bind the current source body, explicit acceptance items, latest actionable event and blocked run, latest evidence comment ID/hash, non-empty checks, current readbacks for every external URL, empty contradiction/irreversible-action lists, false user/product/security ambiguity flags, and a plain-language completion receipt. An explicitly accepted honest blocker may complete only the bounded investigation and may not claim the external bug fixed or close its issue. For compatibility with already-loaded plugin processes, a verified legacy `update` marker is preserved as a source comment, then maps to `specify` in triage or `unblock` while blocked. Never treat comments alone as resolution authority.
- User input is requested only for one exact current ambiguity; clear transitions never wait for a parent chat turn. Record a user decision only from the current user-authored message that directly answers that exact question, with a source-message receipt. Empty clarification responses, synthetic evaluation text, agent-generated comments, and inferred preferences are not user decisions.
- Caretaker/reconcile cards are internal temporary repair records, not user work. After the trusted operator integrates or deliberately supersedes their receipt, archive them and preserve the receipt on the source; do not leave quota-only, process-loss, review-handoff, or already-integrated caretakers visible as active dashboard tasks.
- Run caretaker, routing, and ambiguity fixtures only under an isolated temporary `HERMES_HOME` and board. Never create placeholder tasks, fake user decisions, route receipts, or evaluator fixtures on a live user board.
- Never use an idle LLM loop, `/goal` watcher, or parallel durable ledger for board maintenance.

## Running-worker health boundary

A heartbeat proves only that the claim lease is being renewed; it is not proof of useful progress. Conversely, a quiet task log is not proof of a stall: synchronous `delegate_task` execution can pause the parent task log while owned child sessions continue API calls and tool work in the global agent log.

Before declaring a running task stalled, resolve its worker session and owned descendants. Treat it as active when any parent/child session has recent API/tool progress or when the task log resumes. Do not create a caretaker or reclaim the source in that state. A true live stall requires bounded evidence of no progress across the parent and all owned descendants, no active bounded API/tool call, and no terminal transition; the gateway/runtime owner should then terminate or block the run so the normal blocked-event caretaker path can reconcile it. Do not make the caretaker a second process supervisor.

## Candidate contract

Create a caretaker only when all hold:

1. source is `blocked` or `triage`;
2. latest actionable event is current and has a concrete non-dependency cause;
3. source is not caretaker-authored;
4. no non-archived caretaker already owns `board + source task + event id`;
5. board/profile/resource concurrency permits a new worker.

Use an event-scoped identity such as `kanban-caretaker:v1:<board>:<source>:<event-id>`. Normal completions and ordinary dependency waits remain native-dispatcher work.

## Atomic deduplication

Do not rely on a pre-check plus `idempotency_key`. A non-unique index and a check outside the write transaction allow simultaneous hook/cron calls to insert duplicates.

Serialize the complete check/create boundary with a bounded cross-process OS lock scoped by board, then repeat the existence check while holding the lock. Release in `finally`; OS ownership must release after process death. A lock timeout is a recoverable repair error, not permission to create without the lock.

Required probe: start at least eight simultaneous contenders for one source event and assert one creation plus seven existing results, with one stored idempotency row.

## Cross-card authority and resolution provenance

A delegated caretaker may read and comment on its source, but Hermes intentionally prevents it from mutating another card's status. Do not clear identity guards or run a privileged subprocess to evade that boundary.

The caretaker records receipts on the source, then completes its own run with an exact structured summary:

```text
KANBAN_CARETAKER_RESOLUTION source=<task-id> event=<event-id> action=<terminal_review|complete|unblock|specify|archive|keep_blocked> recommendation=<concise action and decisive evidence>
```

The operator scan may act only after verifying:

- caretaker task `created_by` is the caretaker owner;
- caretaker task is done;
- joined run is successful/completed;
- caretaker idempotency key exactly matches board, source, and event;
- source is still actionable;
- marker event is still the source's latest actionable event.

Arbitrary source comments, failed runs, mismatched keys, stale events, malformed markers, and non-caretaker tasks are untrusted and ignored. The operator scan applies the exact supported operation and requires state readback; it never guesses from prose or bypasses a rejected Kanban gate. `keep_blocked` is terminal evidence for the current caretaker and must not wake the user.

### Parent/operator reconciliation runbook

Treat the desired board state—not one command's return code—as the idempotency contract:

1. Independently re-read the source event, acceptance criteria, receipts, and current task status.
2. Select only supported transitions. `complete` accepts `ready`, `running`, or `blocked`; an evidence-complete `triage` task must first use `specify`, then be read back as `ready` after parent gating before completion. Never force a triage row directly to done.
3. If the source is already `done` or `archived`, record it as already reconciled instead of retrying or reporting a false failure.
4. For a batch of independent repairs, execute and read back each action separately. Preserve successful side effects when another action fails; retry only the unmet desired state.
5. If the parent terminal/subprocess surface still carries delegated-child lineage after child completion, do not clear or spoof the marker. Use a fresh supported parent/operator process. For portable script-only one-shots, prefer Python plus argument-vector subprocess calls when a native Windows path would otherwise cross a Bash boundary.
6. Remove the temporary one-shot job/script after the final receipt. A failed temporary job is evidence, not a recurring recovery mechanism.

## Ambiguity boundary

Only this exact blocked-reason contract represents a user decision:

```text
KANBAN_CARETAKER_AMBIGUITY source=<task-id> question=<one concise question>
```

Generic operational blocks, tool failures, and cross-card guard messages are not questions. Select at most one current ambiguity by board priority/age; do not dump board state or ask the user to inspect it. Delivery is action-triggered: the caretaker's native `blocked` event is consumed through its inherited source subscription and wakes the originating Desktop/TUI session. `pre_llm_call` remains only a next-turn fallback for unsubscribed legacy cards, not the proactive delivery mechanism.

`pre_llm_call` handlers must return nothing inside:

- dispatcher-owned Kanban worker turns (`HERMES_KANBAN_TASK` or equivalent ownership predicate);
- in-process delegated children (`agent.delegation_context.is_delegated_child_process_context()`);
- delegated subprocesses carrying `HERMES_DELEGATED_CHILD_CONTEXT`.

Checking only environment variables misses same-process `ContextVar` delegation.

## Cron and plugin activation

- Hook delivery is proven only in a process that has already discovered the plugin. A standalone `hermes kanban block` command is not proof.
- Verify immediate hook delivery through a preloaded lifecycle dispatcher under an isolated `HERMES_HOME`.
- Verify the repair adapter separately by running it twice: first run creates missing caretakers, second run creates none.
- Create the recurring repair schedule directly (for example, `every 1m`). Read back script path, no-agent mode, and infinite/null repeat count; changing a one-shot schedule can preserve its finite repetition metadata.
- A newly enabled plugin requires a fresh discovering process. Do not restart a dispatcher while legitimate workers are active; defer restart or prove the restart does not terminate them.
- If `hermes gateway restart` refuses because the caller is a gateway descendant, use a separate OS shell rather than bypassing the guard. Record the old PID, submit the restart once, and verify the authoritative PID before retrying when terminal input is `unverifiable`; a changed PID proves success even if the shell rendered no result. Close only the temporary shell/tab created for the restart.

## Minimum verification matrix

1. healthy board: no output, no task creation, zero LLM sessions;
2. actionable blocked event: one bounded high-priority caretaker;
3. dependency block and caretaker-authored block: ignored;
4. hook/cron concurrency: one stored caretaker;
5. repeated repair scan: no duplicate;
6. operational caretaker block: no user wakeup; an event-current `gave_up` caretaker receives at most one bounded automatic repair retry, then its integrated/superseded reconcile card is archived rather than left as active dashboard work;
7. exact ambiguity: one native notification/question only, delivered through an inherited source subscription; empty responses, evaluator output, agent-authored comments, and synthetic fixtures cannot produce a `User decision` receipt;
8. provider usage exhaustion: task remains retryable without failure-count inflation and resumes after reset, including across gateway relaunch; no user-facing reconcile task is created;
9. forged source comment: ignored;
10. failed run, mismatched key, stale event, or completed source: ignored;
11. successful provenance-bound `unblock`, `specify`, narrow `terminal_review`, or non-purging `archive`: exact supported command applied once with readback; ordinary `complete` remains parent-reviewed; legacy `update` preserves its recommendation before continuing;
12. same-process delegated child and subprocess child: no injected context;
13. installed source hashes, plugin hook count, one-minute cron recurrence, active source/caretaker subscription inheritance, and one automatic ready-to-running transition read back from live state.
