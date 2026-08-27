# Hermes Kanban caretaker

The caretaker keeps a Hermes Kanban board moving without a standing `/goal` loop or an agent-backed polling job.

## Runtime shape

1. The gateway dispatcher remains the sole normal scheduler. It promotes dependencies, retries provider-usage exhaustion without failure inflation, reaps stale claims after relaunch, and spawns ready/review workers.
2. The native `kanban_task_blocked` plugin hook immediately creates one idempotent caretaker card for an actionable repeated-blocker or `triage` source episode.
3. Dependency waits and caretaker cards are excluded, preventing recursion. A bounded cross-process file lock serializes the idempotency check/create boundary because the current Kanban schema does not uniquely enforce `idempotency_key`.
4. Every caretaker inherits the source task's native notification subscriptions. An exact ambiguity blocker therefore wakes the originating Desktop/TUI session through Hermes's existing Kanban notifier; no parallel alert channel is created.
5. A one-minute script-only cron scan is repair, not the normal response path: it repairs events missed while the plugin or gateway was offline, rearms an event-current operationally crashed caretaker once, and applies provenance-verified `terminal_review`, `unblock`, concrete triage `specify`, or non-purging `archive` handoffs through the supported operator CLI. Ordinary `complete` remains parent-reviewed. It never retries an exact ambiguity as an operational failure.
6. A `pre_llm_call` hook remains a next-turn fallback for unsubscribed legacy cards. Resolution provenance must be a successful caretaker-owned run whose idempotency key matches the source event; arbitrary source comments are ignored. Only exact caretaker ambiguities become user questions. Kanban workers and delegated children are excluded.

Normal completions do not create caretaker cards: Hermes already recomputes dependent readiness after completion. A task that can be resolved by the native dispatcher should not spend an orchestration turn.

## Source and deployment

The source package is `integrations/hermes/kanban-caretaker/`. Deploy it to the active profile as:

- plugin: `$HERMES_HOME/plugins/kanban-caretaker/`
- recovery adapter: `$HERMES_HOME/scripts/kanban-caretaker-scan.py`
- local settings: `$HERMES_HOME/plugins/kanban-caretaker/settings.json`

`settings.json` is install-specific and is not committed. Start from `settings.example.json`; use absolute workspace and Hermes-home paths.

Enable the native plugin and schedule the repair scan:

```text
hermes plugins enable kanban-caretaker
hermes cron create "every 1m" --name "Kanban caretaker recovery scan" --script kanban-caretaker-scan.py --no-agent --deliver local
hermes gateway restart
```

The script produces no stdout on a healthy or successfully repaired scan. Errors exit nonzero. Creation/error receipts are bounded in `$HERMES_HOME/reconciliation/kanban-caretaker-events.jsonl`.

## Caretaker contract

A caretaker must inspect the source card, dependencies, comments, runs, workspace, and relevant native-thread evidence. Narrow or thread-local implementations remain partial evidence until reconciled against the broader outcome. The worker may comment on another card but must not bypass Hermes's cross-card mutation guard. It completes its own verified run with exactly this summary:

```text
KANBAN_CARETAKER_RESOLUTION source=<task-id> event=<event-id> action=<terminal_review|complete|unblock|specify|archive|keep_blocked> recommendation=<one concise operator action and decisive evidence>
```

The operator scan verifies caretaker ownership, successful-run provenance, idempotency key, and current event identity before applying every concrete recommendation through the supported CLI; exact post-action readback must match. `specify` is valid only for a triage source whose correction no longer depends on user judgment. For compatibility with already-loaded plugin processes, a verified legacy `update` marker becomes a source comment followed by `specify` in triage or `unblock` while blocked. `archive` never purges. `keep_blocked` records a valid gate without waking the user. Ordinary `complete` is surfaced for parent review but is not auto-applied.

`terminal_review` is the only automatic completion action. Its successful caretaker run metadata must bind the source task, latest actionable event and blocked run, current body and explicit `Acceptance:` line hashes, every acceptance item to non-empty evidence, and the latest source evidence comment by ID and hash. It must also record non-empty checks, current readbacks for every external URL in the source body, empty contradiction and irreversible-external-action lists, explicit false user/product/security ambiguity flags, and a plain-language receipt with what was done, how it was checked, and remaining external follow-up. Any missing or stale field fails closed. An explicitly accepted honest blocker may complete the bounded investigation, but its receipt may not claim the external bug fixed or issue closed.

If—and only if—a user decision changes the correct action, the caretaker blocks itself with:

```text
KANBAN_CARETAKER_AMBIGUITY source=<task-id> question=<one concise question>
```

The caretaker's native blocked event delivers only that question into the subscribed originating chat. The next-turn hook is a fallback for legacy unsubscribed cards. The user is never asked to inspect the board, and a rejected judge is never bypassed.

## Verification

```text
python -m unittest discover -s tests -p 'test_kanban_caretaker.py' -v
python -m py_compile integrations/hermes/kanban-caretaker/*.py
```

Test an installation against a temporary `HERMES_HOME`; do not create synthetic blocked cards on the live board merely to probe the hook.
