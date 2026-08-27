# Comparative research: public Sol agent and DAG designs

Date: 2026-08-26

## Conclusion

No public implementation justified replacing the current DAG decomposition or its immutable exact-route receipts. The strongest external ideas were narrower operational controls: explicit acceptance/stopping criteria, a durable pre-spawn launch claim, and actionable blocker metadata. Those three ideas entered schema version 5; schema version 6 subsequently added an independent run manifest, a pinned catalog snapshot, and exact catalog-tuple validation after adversarial review exposed coordinated-rewrite and forged-receipt gaps.

No candidate published a matched evaluation against this DAG on the same tasks, models, effort, latency, and cost. Claims below are therefore architectural/source findings, not evidence that a candidate produces better end results.

## Requirement vector

A better design had to preserve:

- one portable DAG/state owner with thin Codex, OMP, and Hermes adapters;
- one exact provider/model/reasoning receipt selected before launch;
- receipt reuse on retry/resume, with no automatic effort escalation;
- non-spawning workers and bounded concurrency;
- immutable run plans, dependency gating, bounded context injection, terminal handle closure, and fail-closed route verification;
- a small local implementation rather than a new daemon unless the daemon produced a measurable benefit.

## Search strategy

| Query path | Purpose | Useful hits | Misses/limits |
|---|---|---|---|
| `GPT-5.6 Sol agent DAG`, `gpt-5.6-sol orchestration GitHub`, `Sol coding agent workflow` | Find Sol-specific designs without anchoring on a known repo | Sol Advisor, Sol-Orchestrator, Sol-Governed Codex | Sparse ecosystem; several projects are new and lightly validated |
| `open source coding agent DAG persistence`, `multi agent workflow resume exact routing`, `agent orchestration durable DAG GitHub` | Find stronger neutral runtime designs | OpenAI Symphony, Open Dynamic Workflows, Codex Worker | Most durable engines do not pin exact provider/model/effort receipts |
| `GPT-5.6 Sol prompting agents`, `GPT Sol verifier decomposition`, `gpt-5.6-sol best practices` | Find quality improvements that do not depend on effort escalation | OpenAI prompt guidance, risk-gated reviewer patterns | No matched public Sol benchmark against this DAG |

Canonical repositories were cloned and inspected at these commits:

- Sol Advisor: `37b75cad535abdd46531f0227483a8842d045ab8`.[2]
- Sol-Orchestrator: `9a9a644`.[3]
- Sol-Governed Codex: `5ed426dde20fd3c398c7d25bdd00991e33910e7b`.[4]
- Codex Worker: `3d1c224`.[5]
- OpenAI Symphony: `8001b52e3062495a16e520e4ceaf8f9de868c4d0`.[6]
- Open Dynamic Workflows: `972bb98`.[7]

## Candidate comparison

| Candidate | Strong ideas | Conflict/gap versus current contract | Verdict |
|---|---|---|---|
| Sol Advisor | Defaults to solo work, uses a single bounded auxiliary when useful, pins named implementer/reviewer roles, and keeps the final Sol reviewer read-only.[2] | Its routing is role/profile based rather than a hash-bound per-node receipt, and its documented high-complexity lane is an escalation policy. | Keep selective review and read-only reviewer ideas; reject its routing/escalation structure. |
| Sol-Governed Codex | Requires observable acceptance criteria, structured `PASS/REVISE/BLOCKED` review, bounded depth/threads, no descendants, and a prompt-footprint budget.[4] | It is a skill/profile contract, not a persisted DAG runtime; profile/model identity is mutable outside a run receipt. | Adopt explicit acceptance criteria. Existing DAG already enforces bounded concurrency and non-spawning workers. Keep structured verdicts as a future output-contract option, not a universal node format. |
| Sol-Orchestrator | Versioned graph replacement, durable goals above workflows, legal next actions, write grants, changed-file evidence, review/blocker state, and startup recovery are implemented and tested.[3] | It is an OpenCode-specific second state owner. Its replacement model conflicts with immutable run plans, and inspection reproduced a path that can accept a worker without a durable result. It also lacks the current exact route receipt guarantee. | Do not transplant. Reconsider versioned replacement only if immutable new runs become a demonstrated bottleneck. |
| Codex Worker | Strong mechanical forwarding gates, provenance checks, idempotent usage logging, and a child-side identity record that closes the spawn-to-record race.[5] | Unix-heavy runner and Claude hook assumptions reduce portability; it is a forwarding harness, not a DAG. | Adopt the lifecycle lesson as an atomic pre-spawn claim plus claim-token handle attachment. Keep host adapters native. |
| OpenAI Symphony | Durable scheduler authority, bounded same-task retries with backoff, tracker reconciliation, isolated workspace lifecycle, continuation turns, metrics, and explicit blocked/retry state.[6] | It is an issue-tracker service, not a small portable DAG helper; it does not provide immutable exact model/effort receipts. | Adopt actionable blocker metadata. Keep retries on the same receipt. Do not import the service/supervisor architecture. |
| Open Dynamic Workflows | SQLite/WAL persistence, deterministic node cache keys, timeouts/cancellation, token/cost budgets, structure-preserving context compaction, sandboxed generated orchestration scripts, and Windows-aware daemon lifecycle.[7] | It adds a daemon, API, sandbox, and provider layer; model aliases and retries are not the current receipt contract. Its full daemon suite did not complete cleanly on this Windows inspection. | Useful reference if a reboot-surviving supervisor or token accounting is later required. Do not replace the small state owner now. |

## Adopted changes

### 1. Observable acceptance and stopping conditions

OpenAI's GPT-5.6 prompt guidance recommends explicit success criteria, stopping conditions, and autonomy boundaries.[1] Sol-Governed Codex independently encodes the same idea in its plan/review contracts.[4]

Implemented:

- every new receipt-routed task requires a non-empty `acceptance` list;
- acceptance criteria are preserved in the rendered worker prompt;
- all four shipped templates now contain role-appropriate criteria;
- the parent still owns final acceptance.

### 2. Atomic pre-spawn launch claims

Codex Worker treats the spawn-to-record window as a correctness problem and records child identity before the final exec.[5] The portable equivalent is now:

1. atomically create `tasks/<id>/launch.claim` with exclusive creation;
2. persist `launching`, a random claim token, and the attempt count before native spawn;
3. require the same token when attaching the native handle;
4. reject duplicate claims and mismatched/missing claim files;
5. require host reconciliation before retrying `launching` work;
6. remove the claim only after terminal state is durably written.

This prevents duplicate routed launches without introducing a cross-host daemon. A crash after claim but before spawn intentionally strands the task in `launching`; it must be reconciled rather than guessed safe.

### 3. Actionable blocker state

Symphony retains explicit operational reasons for blocked and retried work rather than exposing only a generic failed status.[6]

Blocked descendants now persist:

- `blocked_by`;
- `blocked_reason`;
- `blocked_at`;
- `requires_operator`.

A successful dependency retry clears those fields and restores the descendant to `pending`.

## Explicit non-adoptions

- **No DAG replacement/replanning inside a run.** Immutable plans plus a new linked run remain simpler and safer than version mutation.
- **No automatic effort escalation.** Retry means the same exact receipt; unresolved work returns to the parent/human.
- **No universal Sol reviewer.** Independent review remains risk-gated because attaching it to every node increases cost and latency without matched evidence.
- **No daemon, SQLite migration, or sandbox.** Those are justified only if reboot survival, token accounting, detached supervision, or untrusted generated orchestration scripts become actual requirements.
- **No inferred model identity.** Host-reported metadata can corroborate a launch, but the hash-bound route receipt remains authoritative.
- **No usage/cost receipt yet.** Codex and OMP expose different usage surfaces; adding a portable schema without verified cross-host producers would create decorative rather than reliable accounting.
- **No portable retry timer or process supervisor.** The helper persists bounded attempts and exact receipts, while host adapters own liveness checks, cancellation, and any backoff. Adding timers without a reboot-surviving scheduler would overstate durability.
- **No core-owned workspace manager.** `workdir` remains a declared task boundary; host-native permissions and worktree/session isolation are authoritative. A portable cleanup manager is deferred until all hosts can produce and verify the same lifecycle evidence.

## Verification

Local definitive implementation after adoption:

- `python skills/dynamic-workflows/scripts/test_workflow_state.py` — 47 tests passed;
- routed claim lifecycle covers cross-process-serialized state transitions, atomic concurrent claiming, orphan-claim reconciliation, duplicate prevention, bounded single-line handle validation including Unicode separators, single-use token attachment, stale-completion rejection, manifest-bound plan/catalog integrity, terminal claim cleanup, and same-receipt retry;
- blocker tests cover blocked metadata and clearing after dependency retry;
- the adapter validates every receipt against `route-decision.schema.json` before producing native launch mappings, in addition to semantic hash/binding checks; invalid pin status, missing required metrics, and unknown fields fail closed;
- `python -m pytest tests/test_route_adapter.py tests/test_route_selector.py tests/test_tools.py -q -o addopts=` — 46 tests plus 11 subtests passed;
- `python tools/validate.py` — 7/7 skills valid;
- compileall and `git diff --check` — passed.

Candidate runtime verification was deliberately not promoted beyond what ran locally. Sol-Orchestrator's focused core tests/typecheck ran after dependency installation, while its full suite/build had environment-specific failures. Symphony could not run because Elixir/Mix is not installed. Sol Advisor and Sol-Governed validators were partially blocked by Git-Bash path/tool assumptions. Open Dynamic Workflows' core and selected daemon tests ran, but its full daemon suite did not complete cleanly. These limits reduce confidence in wholesale adoption and do not affect the source-level design comparison.

## Sources

[1] https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6
[2] https://github.com/DannyMac180/sol-advisor
[3] https://github.com/ReyJ94/Sol-Orchestrator
[4] https://github.com/BusyBee3333/sol-governed-codex
[5] https://github.com/chrisb4096-alt/codex-worker
[6] https://github.com/openai/symphony
[7] https://github.com/Suraj1235/open-dynamic-workflows
