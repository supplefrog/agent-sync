# Human-off orchestration control plane

Use this reference when repeated “blocker → caretaker → parent → manual patch” episodes indicate a state/authority defect rather than another missing recovery case. Re-check the live source before implementation; these observations describe the audited Hermes Kanban shape and may evolve.

## Audited gaps

- `review` is a valid task state and the dispatcher can claim it, but ordinary workers have no general submit-for-review transition. Review dispatch is PR-specific, so workers use `blocked` for verification handoffs.
- Typed block reasons already distinguish dependency, transient, needs-input, and capability cases. Overloading `blocked` with completed work destroys that distinction and makes caretaker prose inference necessary.
- The dispatcher caps global/profile concurrency but does not exclude two tasks with the same effective writable `dir:` workspace. A repository without a baseline commit cannot use Git worktrees; it must serialize or use a runtime-owned temporary copy.
- Worker context includes the assignee’s most recent completed tasks regardless of relevance. Recency is not a relevance policy and can displace task evidence.
- Delegation, Kanban, DAG, thread, and auxiliary surfaces expose different routing controls; a global delegated-child route cannot express mixed task requirements.
- A parent/controller must retain operator authority while its delegated children run. Child mutation guards remain mandatory; context-local delegation state must reset at the child boundary rather than leak into the parent continuation.

## Target contract

Keep Kanban as the sole durable authority. Separate deterministic control from model judgment:

1. **Intake** receives the current request, compact user preferences, active board summary, and targeted retrieval. It proposes a typed board delta; a deterministic validator checks ownership, deduplication, dependencies, and permissions.
2. **Execution** receives only the task contract, direct handoffs, selected evidence, and writable ownership. It cannot mutate sibling cards.
3. **Review** receives acceptance criteria, artifacts/diff, checks, current external readbacks, and the producer receipt—not exploratory reasoning. Deterministic checks run first; an independent reviewer is invoked only when judgment remains.
4. **Control** applies idempotent transitions with current-event/provenance checks and post-action readback.
5. **Learning** admits only verified reusable corrections to the owning skill/evaluation; raw histories stay searchable.

Use machine-readable outcomes:

- dependency wait → `todo`/parent gating;
- transient quota/tool/runtime problem → scheduled retry or `ready`;
- result awaiting verification → `review`;
- accepted review → `done` plus receipt;
- rejected review → `ready` plus bounded correction evidence;
- bounded investigation complete but external evidence pending → execution `done`, separate external watch retained;
- unresolved product/security/authorization choice → `blocked` with `needs_input` and exactly one question.

Only the last case interrupts the user. Completion and automatic-repair receipts remain on Kanban and enter an on-demand or batched digest; do not push routine completions individually unless requested.

## Native-first repair

Before growing caretaker actions, inspect whether the native review state, dispatcher, lifecycle events, notifier, and worker tools can own the behavior. Prefer completing/generalizing that path:

- worker submits a structured result to `review`;
- reviewer accepts or returns the same card for correction;
- caretaker handles missed events, stale claims, and deterministic recovery only;
- parent/operator policy performs privileged mutations; delegated workers never bypass cross-card guards.

Do not install another workflow engine merely to copy this pattern. Temporal/LangGraph-style separation of durable state, deterministic control, activities, review, and human signals is transferable; Kanban already owns the event ledger and scheduler. LangGraph may be admitted only as a task-local execution adapter when a concrete workflow needs its checkpoint/subgraph primitives and a staged comparison beats the existing host-native executor. It must not own fleet state, routing policy, memory, stakeholder delivery, or cross-agent handoff. LangChain is not the common agent contract.

## Workspace contract

Normalize the effective writable root before claim. Acquire one lease per mutation domain, not merely per repository label. Same root never runs concurrently. Use a Git worktree only after proving a baseline commit and clean ownership; otherwise serialize or create a runtime-owned temporary copy with an explicit integration receipt. Release/delete temporary work only after accepted evidence is integrated.

## Context contract

Every durable work unit carries an agent-neutral packet: outcome, hard constraints and approvals, current state, dependencies, material decisions, artifact/evidence references with provenance and freshness, acceptance checks, unresolved questions, and the next allowed action. Treat the card as one evolving front-end conversation while it is in intake/triage: the first prompt is not a frozen specification. Reconcile later brainstorming, corrections, rejected alternatives, and rationale into an append-only intent/decision lineage that distinguishes user statements, evidence, inference, superseded directions, commitments, and open questions. For material new work, use the research-first intake gate before execution; repetitive/mechanical work may reuse an established procedure with explicit checks. Kanban plus referenced artifacts is authoritative; a chat transcript, model reasoning trace, generated summary, or compressed handoff is a lossy projection and never the task database.

Give each Hermes, Codex, OMP, DAG, or optional LangGraph worker a scoped projection of that packet and only the evidence needed for its role. A different supported host must be able to resume the work from the packet without the originating chat. At handoff boundaries, integrate new decisions/evidence into the packet, record omissions and uncertainty, then retire an agent-created thread when no longer referenced. Summarization is a lossy view for people or bounded workers, not the mechanism that preserves orchestration.

Do not inject “last N tasks” solely because the assignee matches. Retrieve history by current outcome, project, symbol/artifact, dependency, or explicit ownership and attach provenance plus freshness. Keep intake/control, producer, independent reviewer, and stakeholder brief contexts distinct. The main chat is a stakeholder and control surface, not the execution workspace.

Material architecture or irreversible direction gets one bounded adversarial review: present the strongest credible alternative, attack the preferred design’s authority boundaries and failure modes, and look for decision-changing counterevidence. Stop when the objections are resolved or converted into explicit risks/checks. Do not add adversarial theater to routine implementation or reopen settled choices without new evidence.

## Stakeholder brief contract

Treat the user as the captain of the whole task fleet, not as an implementation reviewer.

- Every status answer starts with four plain-language groups: **Working**, **Waiting**, **Done**, and **Needs you**. Omit empty groups. State whether the approved outcome is live, staged, or not started.
- Build the brief from a fresh authority read: enumerate every material nonterminal workstream plus recent decision-bearing completions/rejections, then reconcile dependencies and next transitions. Maintain a material-lane register anchored in the stakeholder's broad outcome, so umbrella/meta work, blocked subordinate lanes, accepted research, and legacy-provisional completions remain visible even when no current card is running. Never report only the current chat topic, most recently changed card, or workstreams the user remembered to name. A missing material lane is a failed status report.
- Before accepting a worker or reviewer PASS, compare the frozen criteria and decision-event hash chain against every later intent-owner event on the authoritative card. A user correction or scope clarification that arrived after freeze—or during the final worker/reviewer run—invalidates terminality until it is represented as an explicit amendment, mapped to decision scope and evidence lanes, regenerated, and independently reverified. A comment existing beside the artifact is not proof that the artifact incorporated it.
- Treat historical `done` as a lifecycle fact, not automatic evidence quality. When a stronger gate is adopted, classify only load-bearing legacy outcomes as verified, provisionally valid, superseded, or failed; do not rerun every old task, but do not let an unreviewed terminal receipt silently govern a current decision.
- Prove execution state. **Working** requires a live claim/run and fresh activity readback; `ready`, assigned, staged, planned, or a worker's prose promise belongs in **Waiting** until execution is observed. Verify the assignee exists and is spawnable before dispatch; automatically use supported reassignment/recovery policy for phantom profiles or report the operational blocker. The user must not be the monitor that discovers stranded work.
- Explain direction across cards: what the system is doing first, what follows, and why that order protects time, cost, quality, or dependencies. Do not dump card IDs, caretaker vocabulary, reviewer prose, logs, diffs, or code snippets unless the user asks. Abstraction may remove routine execution detail; it must never remove unmet acceptance checks, missing comparisons, failed checks, unresolved decisions, or material evidence caveats.
- Any recommendation, rejection, promotion, or retained incumbent from a nondeterministic worker requires an auditable decision trace: options actually evaluated, criteria with pass/fail/not-run state, evidence references, material uncertainty, and why the current state changes or remains unchanged. Label the result as a matched comparison, candidate-only gate, or no comparison. Never report “A beat B” when only A was tested, or translate “candidate failed its own gate; no change” into an incumbent victory. If uncertain whether a fact is decision-bearing, preserve it by default or ask the user; never silently abstract it away.
- Do not hide load-bearing choices as implementation details. Hosting/locality, free-versus-paid service, privacy/data location, irreversible installation or promotion, architecture scope, external writes, and material quality/cost/latency trade-offs are stakeholder decisions.
- For each stakeholder decision, state: **decision**, **recommendation**, **why it matters**, **alternatives**, and **what happens next**. Explain technical terms in ordinary language. Ask one current decision at a time when answers are sequentially dependent; otherwise present a small consolidated decision set for the fleet.
- Make reversible code-level choices autonomously inside the approved direction. Surface them afterward only when they change risk, outcome, cost, maintenance, or future options.
- When the user's existing preference already determines the choice, apply it and report the choice before promotion; do not manufacture another approval gate. Example owner rule: prefer a genuinely lifetime-free cloud service when verified, otherwise the simplest supported local setup—never silently convert starter credits into “free cloud.”
- Push a stakeholder brief to the originating chat automatically when a lane starts, materially changes direction, enters review, encounters a genuine blocker, needs a decision, is promoted live, or completes. The user should not have to request status. Batch routine/no-impact transitions and deduplicate unchanged state; native event delivery is preferred, with a stable-output monitor only as recovery.
- Treat instruction growth as a regression risk. Before promotion, compare the candidate against a lean baseline, remove redundant model-specific compensations, and use deterministic checks or an independent evaluator. Do not let the same model author, judge, and permanently encode its own quirks without held-out evidence.

## Verification matrix

Stage against the current baseline and include held-out cases:

1. true decision interrupts once;
2. review-ready result auto-verifies and completes or returns one correction;
3. dependency/transient/quota/relaunch/stale-claim cases recover without user input;
4. external-evidence boundary closes bounded execution and retains the watch;
5. forged, stale, contradictory, or incomplete receipts fail closed;
6. two same-root writers cannot run concurrently, including an uncommitted repository;
7. delegated child cannot mutate Kanban while the parent retains controller authority;
8. unrelated assignee history is absent from worker context; relevant retrieval is present;
9. routine completions are recorded but do not interrupt;
10. restart/replay remains idempotent;
11. a task started in one supported agent resumes correctly in another from the durable packet without the originating chat;
12. lossy or stale summaries cannot overwrite authoritative decisions, evidence, or open questions;
13. material lifecycle events reach the originating stakeholder surface, and quota-replenished work resumes without a manual nudge;
14. a candidate-only gate failure is reported as “no change,” not as an incumbent win;
15. stakeholder briefs expose missing/not-run acceptance checks and link the auditable decision trace;
16. a status request includes every material active lane and recent no-promotion/rejection even when the user names only one workstream;
17. `ready`, assigned, staged, or planned work is never labeled working without a live claim/run and fresh activity readback;
18. a task assigned to a missing or non-spawnable profile is detected and reconciled through supported policy without waiting for the user to notice;
19. an intent-owner amendment arriving after freeze or during final review invalidates the prior PASS until the amendment chain, criteria/scope mapping, evidence lanes, receipts, and fresh independent verdict all include it;
20. an accepted broad outcome still surfaces its blocked, waiting, and legacy-provisional subordinate lanes after unrelated context switches, without the stakeholder naming them;
21. a pre-gate `done` artifact may remain terminal operationally but cannot authorize a current architecture/promotion decision until its load-bearing claim is explicitly reclassified under the current gate.

### Probe-harness integrity

For temporary-state lifecycle probes, verify imported modules resolve to the intended candidate tree before interpreting results. Close SQLite handles explicitly (a transaction context does not close the connection), drive delegated-context predicates through the same process/context authority channel production reads rather than only editing a candidate environment dictionary, and assert documented state transitions instead of truthiness from private helpers with no return contract. A harness mismatch is not a product finding. Delete disposable scripts, databases, and baseline worktrees after preserving the observed receipts.

Compare intervention count, verified task success, end-to-end latency, prompt/context size, retries, and total model cost. Promote only on net benefit; retire caretaker exceptions made redundant by the native path.
