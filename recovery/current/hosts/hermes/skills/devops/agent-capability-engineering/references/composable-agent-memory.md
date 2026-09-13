# Composable Personal-Agent Memory

Use when evaluating or designing memory for a personal assistant. The user should continue asking ordinary questions and handing over tasks; memory operates behind that interface and never becomes task authority.

## Research-backed decomposition

Treat memory as modules, not a provider contest:

1. **Evidence substrate** — immutable transcript/artifact references and exact search.
2. **Typed current-state memory** — explicit facts, preferences, goals, and activities with source, confidence, valid-time, observed-time, supersession, and deletion.
3. **Extraction/update** — incremental `ADD / UPDATE / DELETE / NOOP`; preserve old evidence while invalidating obsolete active state.
4. **Retrieval/router** — select exact/keyword, semantic, temporal/entity, or hybrid retrieval by query type; rerank and abstain when evidence is weak.
5. **Derived understanding** — generate hypotheses or summaries on demand from selected evidence; keep inference separate from facts, cite support/counterevidence, attach confidence/expiry, and make it revisable.
6. **Maintenance** — consolidation, contradiction handling, forgetting, deletion, and stale-memory penalties.
7. **Adapters** — expose the same typed contract to different agents/runtimes without making a provider canonical.

## Transferable components

- Hermes/session FTS: raw transcript evidence.
- Kanban/artifact references: authoritative task and decision state; never replace with semantic memory.
- Mem0: incremental extraction and update-operation pattern.
- Hindsight: configurable multi-strategy retrieval/reranking and separation of world facts, observations/experiences, summaries, and beliefs.
- Graphiti/Zep: temporal validity intervals and non-lossy relationship history when relational/temporal workload justifies graph infrastructure.
- Memora/FAMA: penalize use of obsolete or deleted memory.
- KnowMe-Bench / PersonaMem / OP-Bench: evaluate evidence-grounded person understanding, implicit preferences, abstention, and over-personalization rather than treating factual recall as “deep insight.”
- Strong reasoning model: invoke on demand over bounded evidence; do not persist opaque psychological deductions as user facts.

## Evidence and evaluation rules

1. Research primary papers, official repositories/docs, independent evaluations, and existing receipts before running local comparisons.
2. Compare each claim on its owning metric. Recall benchmarks do not prove person understanding; user-model marketing does not prove recall; operational dimensions matter only when they materially affect the intended deployment.
3. Decompose candidates into modules and produce retain/adapt/replace/remove decisions before considering a new platform.
4. Run local tests only for unresolved, decision-changing environment claims such as host integration, exposed provenance, latency, lifecycle cleanup, deletion, and rollback. Do not reproduce standard public benchmarks without a specific evidence gap. If the user says local testing is compensating for inadequate discovery of existing evidence, preserve that distinction: source claims define test targets, but local-first is not their standing preference.
5. Treat vendor benchmarks as directional until methodology, backbones, judges, data, and reproducibility are comparable.
6. A non-hard downside is a weighted tradeoff, not automatic rejection. Hard exclusions are safety, privacy, authority corruption, unbounded cost, or non-reversible state.
7. Prefer the smallest reversible control plane over another database, agent runtime, or generic memory service.

## Utility-first admission gate

Before choosing a provider or reproducing another benchmark, establish whether external memory has enough marginal value to justify existing at all.

1. **Use the real incumbent.** Compare against the user's actual baseline: curated durable memory, exact session search, repository/docs, skills, and task state. A synthetic no-memory arm is a diagnostic lower bound, not the deployment baseline.
2. **Sample real decision points.** Reconstruct moments where material context lived only in earlier work. Cover the user's actual workload—coding, research, architecture, browser/desktop work, scheduling, workflow design, and preference-sensitive decisions—rather than defaulting to one convenient benchmark domain.
3. **Score downstream change, not retrieval.** A recalled fact counts as useful only when it changes, corrects, or independently verifies the resulting answer or action. Restating the active thread, returning a plausible profile, or merely being called is not benefit.
4. **Measure opportunity and harm together.** Record how often external memory had a genuine opportunity to help, how often it helped, latency, context bytes, maintenance/failure burden, stale or cross-project bleed, irrelevant personalization, and authority confusion.
5. **Keep invocation modes separate.** Tools-only/on-demand retrieval is one candidate. Automatic injection is a separately penalized arm because its context and steering costs apply on turns where memory is irrelevant.
6. **Use a placement gate.** No clear marginal improvement => remove or disable the external provider. Occasional deliberate benefit => keep tools-only or isolate a memory profile. Broad repeatable benefit with low contamination => consider selective integration into regular profiles. Do not promote always-on injection from a tools-only result.
7. **Defer provider theater.** Public suites and multi-provider shootouts become relevant only after utility is established and a remaining provider capability could change placement. Researching Mem0, Hindsight, Honcho, or another system does not create an obligation to deploy or locally benchmark it.
8. **Retire the evaluation cleanly.** Once useful findings and unresolved tasks are in a durable report, identify completed topic-only sessions and generated child transcripts separately from mixed-purpose or pending threads. Present one exact deletion batch, honor the user's backup choice, delete after scoped confirmation, and verify both session and message records are absent.
9. **Separate provider state from source evidence before deletion.** Inventory the provider-derived store, original transcripts/artifacts, curated facts, reusable methods, and decision receipts as distinct assets. State plainly when deleting a database or volume makes the accumulated derived store unrecoverable; do not imply that preserved reports or source conversations preserve the provider's internal representations. If future rebuilding matters, require an explicit export or backup decision before destructive cleanup.
10. **Synchronize the canonical decision ledger.** When retirement changes the live disposition, update the repository-owned decision document, cross-host contract, evidence/contradiction ledger, and overview in the same change. Mark superseded deployment evidence as historical rather than deleting it, remove stale claims that the provider remains active, and run the repository's deterministic audit before reporting completion.

### Authority-first retrospective audit

Use complaints such as “you forgot,” “I already said this,” and “that was in another thread” only to generate candidates—not as proof that an external memory store is needed.

1. Query real user messages while excluding compaction summaries, task-list/control records, and generated delegation notices.
2. Deduplicate exact continuation copies before reporting an opportunity rate.
3. Classify the correct authority for every candidate: repository/docs, task tracker or workflow receipt, explicit handoff, skill/procedure, curated user profile, exact transcript/session search, or external semantic/person memory.
4. Separate same-thread failures from cross-thread gaps. External memory should not receive credit for failures caused by ignoring the active thread.
5. Count an external-memory opportunity only when it is the appropriate owner, the baseline did not already expose the fact, and retrieval would change, correct, or independently verify the downstream answer/action.
6. Report the denominator, unique candidate count, owner distribution, clear external-memory wins, and ambiguous cases. A low or zero realized-win count can justify disabling a technically capable provider without claiming the provider itself is ineffective.

### Prompt-cost and operating-mode accounting

Do not compress context cost into one vague number.

1. Measure fixed provider guidance, fixed serialized tool schemas, and dynamic recall/injection separately. Tools-only can still have substantial fixed schema cost; context-only can have little fixed cost but large per-turn retrieval.
2. Report bytes/chars and model-appropriate token counts without treating them as interchangeable. Use the host's prompt-size report before and after a supported configuration change, then attribute the delta with actual prompt blocks/schemas when needed.
3. Resolve omitted configuration fields from implementation defaults and runtime status. Missing `memory_mode`, `auto_recall`, or `auto_retain` keys do not imply those behaviors are disabled.
4. Measure observed dynamic retrieval sizes as well as configured caps. A cap is a risk bound, not typical usage evidence.
5. Re-check the default profile after isolated experiments. Provider or mode drift is a production mutation even when the experiment's bank/profile was isolated.
6. Verify in a fresh session: current sessions can retain the provider tools and prompt block fixed at initialization after the on-disk configuration changes.

### Transparent decision closure and natural reopening

A utility audit should produce a decision receipt, not a black-box verdict or a standing research loop.

1. Name the exact decision level: active by default, tools-only, isolated experiment, deferred, disabled for the incumbent, or disproven for a bounded claim. “Disabled now” is not “memory is useless,” and a provider losing placement is not proof its mechanism never helps.
2. Show the chain from evidence to action: observed opportunities and downstream changes, costs/harms, authority classification, important counterevidence, and which threshold produced the placement. Label inference separately.
3. Publish audit limits. Complaint-trigger mining is good evidence about realized pain but can miss latent benefits that never generated a complaint. Do not turn zero observed external-only wins into proof that no future use case exists.
4. Name plausible but unobserved use classes without promoting them: longitudinal preference or value evolution, semantic recall when exact keywords are unavailable, contradiction/change tracking across long periods, relationship or recurring-routine context, and bounded person-model reasoning over evidence. These are reopen candidates, not deployment justification.
5. Persist a compact receipt with the incumbent baseline, applied state, deferred candidates, why they lost placement, and concrete reopen triggers. Reuse it instead of rerunning provider research or public benchmarks on a schedule.
6. Reopen naturally only when a real task exposes a repeated material gap, the authoritative baseline cannot recover needed context, a provider fixes that exact case in a bounded matched trial, or relevant runtime/provider evidence materially changes. After the test, close the decision again.
7. Distinguish two routers. A persistence intake may route an explicit durable fact to user memory; it does not detect when a live task needs semantic or person-model recall. Do not claim a runtime memory switch exists unless an executable trigger, bounded retrieval path, abstention rule, and receipt are present.
8. Prefer no speculative detector. If concrete misses later recur, admit the smallest on-demand discovery rule first; automatic broad injection remains a separate candidate with its own utility and contamination evidence.

## Local decision receipt (2026-09-02)

- **Applied state:** the default Hermes profile uses curated `MEMORY.md`/`USER.md`, exact session retrieval, skills, repository/docs, and authoritative task state. No external memory provider is active.
- **Why:** the historical deployment showed no repeatable external-only downstream win across the user's coding, research, browser/desktop, scheduling, or planning work. Most observed provider calls were unused, failed, or duplicated context already available elsewhere. Synthetic tests established technical capability, not realized utility.
- **What was not disproven:** bounded semantic recall, longitudinal preference/change tracking, and evidence-grounded person-model reasoning may help when relevant context is absent from the active thread and cannot be recovered reliably from authoritative artifacts or exact session search.
- **Reopen trigger:** a repeated material miss in real work; identify its correct authority first, then run one bounded matched trial against the incumbent. Do not rerun broad provider comparisons or public suites without a decision-changing gap.
- **Placement rule:** occasional demonstrated benefit stays on-demand/tools-only; broad repeated benefit with low contamination can justify selective integration. Automatic injection requires separate evidence that per-turn context and stale steering are worth it.

## Controlled provider pilots

1. **Write the claim before the harness.** Separate documented architecture, vendor benchmark results, independent reproduction, local execution, and inference. A peer-centric data model documents a mechanism; it is not evidence that the provider understands users better.
2. **Resolve the actual model stack.** Record ingestion/extraction model, retrieval/reranker, synthesis or dialectic model, judge, and the host agent model. Matching only the visible chat model is insufficient.
3. **Isolate all state.** Use disposable profiles plus unique banks, workspaces, peers, and sessions. Disable unrelated built-in memory/context injection. Verify the incumbent's live profile and stores remain unchanged.
4. **Do not mix operating modes.** Run explicit tools-only/manual writes as one lane and ordinary conversational auto-retention as another. Recall mode and retention mode may be independent settings; inspect both rather than inferring one from the other.
5. **Use identical held-out cases.** Include exact facts, superseding corrections, implicit preferences with evidence, conflicting evidence, irrelevant-memory rejection, cross-session continuity, provenance, restart durability, latency, and resource use. Score abstention and over-personalization, not just recall.
6. **Cross the credential boundary safely.** Never reuse or transmit a secret pasted into chat or logs; require rotation and direct user entry through the provider's secure setup surface. Treat an uncredentialed arm as blocked, not as a loss. When the user explicitly approves synchronizing an already-rotated credential between local services, transfer it store-to-store through stdin or a native secret store—never command arguments, logs, output, or disposable backups. Update every dependent service, recreate containers when environment variables are baked at creation, and verify with a real provider-backed write rather than key-presence checks.
7. **Verify the whole path.** Provider status or a health endpoint is not enough. Exercise write, durable read-after-write, retrieval, restart, and host-facing tools. If one arm is unhealthy or configured differently, stop rather than publish a mismatched comparison.
8. **Label the comparison by what is actually matched.** Identical payloads and one host agent do not make an algorithm-controlled benchmark when provider-native write/search tools, extractors, embeddings, rerankers, or synthesis models differ. Report that as an end-to-end system pilot. A manual `retain/recall` lane and a conclusion/search lane can compare operational outcomes, but not isolate memory-algorithm quality.
9. **Keep model-selection lanes separate.** For a matched-provider claim, hold the effective ingestion/retrieval stack constant. For a practical “best available” lane, select only models with nonzero account entitlement, verify the exact API model ID in official documentation, and rerun retention plus restart/read. Authenticated quota dashboards may show historical peak-versus-limit rather than real-time remaining capacity; do not mislabel that signal.
10. **Measure lifecycle explicitly.** Record whether each run is cold, warm, or fresh-process; include provider/service startup when the user cares about end-to-end responsiveness. With one trial per arm, publish latency as directional operational evidence, not a stable performance estimate.
11. **Clean up explicitly.** Stop temporary keepalives and services, remove generated sessions/state when approved, and report anything intentionally retained. A prepared arm is not a completed experiment. Enumerate all destructive cleanup targets before asking, obtain one scoped consent where the host permits, batch idempotent deletions/stops, and verify absence afterward. Do not make the user repeatedly restate blanket consent because the workflow emitted a chain of avoidable command cards.
12. **Separate user-model claims from retrieval.** Include at least four arms: no-memory lower bound; gold-evidence oracle; raw retrieval plus one common evaluator; and provider-native representation/dialectic. When available, split a static peer representation plus common evaluator from native dialectic. A weak search arm with a strong dialectic arm is evidence of reasoning beyond retrieval; a tie is not.
13. **Freeze adversarial labels before outputs.** Longitudinal fixtures should include stable cross-domain principles, context-specific preferences, a genuine preference update, bounded temporary exceptions, weak distractors, and unsupported-choice abstentions. Keep event IDs and explicit counterevidence IDs in the fixture.
14. **Score protocol and reasoning separately.** Record held-out choice accuracy, confidence/Brier calibration, evidence precision/recall/F1, counterevidence misses/false citations, abstention, and format compliance. If a provider emits a valid answer plus duplicated or trailing output, score the first valid object semantically while marking protocol compliance false.
15. **Checkpoint rate-limited runs.** Persist after each complete case, support resume without duplicate ingestion, and separate one-time ingest/derivation readiness from per-query latency. A daemon reset must not consume the whole quota again.

## Operational diagnostics from validated pilots

- If a local embedded daemon restarts on every fresh process, compare saved and desired configuration by key name before changing packages. Runtime-owned fields such as assigned ports or PIDs must not count as desired-config drift; add a regression proving that real model/provider changes still trigger restart.
- A “server support is not installed” wrapper error can be a dependency-range conflict rather than a missing extra. Inspect the package metadata and installed major version, align to the declared range, rerun the full provider test file, and run dependency consistency checks. Capture only a validated fix, not failed install attempts.
- For end-to-end person-model evidence, preserve separate conclusions for retrieval utility, static representation quality, native reasoning quality, provenance, and operations. Do not force one universal memory winner when different modules win different use cases.

## Realized-impact audits

A provider being configured, observing messages, or building a profile is not evidence that it helped. Before proposing another synthetic or domain-specific benchmark, inspect realized influence across the user's actual work:

1. Resolve the operating mode first. In explicit tools-only mode, passive observation/storage cannot affect an answer unless a memory tool is called; cadence settings do not imply automatic dialectic injection.
2. Count actual memory tool calls by operation, session, date, and explicit failure result. Distinguish profile/card maintenance, raw search, writes/conclusions, context injection, and native reasoning.
3. Trace each successful memory result into the immediately following answer. Record what the answer used, whether the same information was already in the active thread/tool query, and whether any decision or recommendation changed. A query that restates all relevant history weakens causal attribution.
4. Search stored prompt/context artifacts for automatic injection, but state storage limitations: absence from persisted prompts is not proof that a runtime never injected context.
5. Separate **capability** (a controlled test shows the system can help) from **realized value** (the deployed configuration actually invoked that capability and improved work). Passive stores with failing or unused retrieval paths have little demonstrated value even if their architecture is sophisticated.
6. Sample real decisions across the user's full workload—research, architecture, coding, desktop/browser, scheduling, workflow design, and personal tradeoffs—rather than defaulting to another coding-only benchmark. At each decision point compare no memory, retrieval plus one common evaluator, static representation, and native reasoning; score useful change, active-thread restatement, stale bleed, irrelevant personalization, and latency/context cost.

## Interpreting common-evaluator memory arms

- A raw-retrieval arm followed by one common evaluator is a legitimate production candidate, not merely a benchmark control. In an agent, retrieval can feed the normal main model and avoid a second provider-native synthesis call.
- If retrieval plus the common evaluator ties native dialectic on held-out choices, report a tie for decision quality. Do not declare dialectic superior merely because its architecture is more specialized.
- Check retrieval selectivity separately. Perfect choices from a small history may come from returning nearly the entire corpus; scale, stale-memory, and context-cost behavior remain unproven.
- Evidence F1 is higher-is-better and measures citation-set fidelity, not choice correctness. Report precision and recall where useful. When both gold and predicted citation sets are empty, the conventional score is `1.0`; condition aggregate provenance claims on evidence-bearing cases so abstention items do not make a no-memory arm look evidence-grounded.
- Losing original event IDs while retaining enough synthesized content to answer correctly is a provenance failure, not necessarily a retrieval or decision failure. Keep these conclusions separate.

## Benchmark routing

- Factual/multi-session/temporal/update/abstention: LongMemEval or LoCoMo.
- Obsolete/deleted memory and mutation: Memora/FAMA.
- Person-level motivation/principle inference with evidence: KnowMe-Bench.
- Implicit preference adherence: PersonaMem/PrefEval.
- Over-personalization and false inference: OP-Bench or equivalent abstention/adversarial cases.
- Real task continuity: task-scoped held-out cases grounded in authoritative task/events, not memory-generated status.

## Primary evidence bank

- Agent-memory modular study: https://arxiv.org/abs/2606.24775 — representation/storage, extraction, retrieval/routing, maintenance; no architecture dominates all workloads.
- Hindsight: https://arxiv.org/abs/2512.12818 — structured networks and retain/recall/reflect; headline evaluation mainly covers long-horizon recall, updates, temporal reasoning, and abstention.
- Mem0: https://arxiv.org/abs/2504.19413 — incremental extraction/consolidation and cost/latency tradeoffs.
- Graphiti/Zep: https://arxiv.org/abs/2501.13956 — temporal graph validity and category-specific gains/regressions.
- Memora/FAMA: https://arxiv.org/abs/2604.20006 — obsolete-memory reuse and forgetting-aware evaluation.
- KnowMe-Bench: https://arxiv.org/abs/2601.04745 and https://aclanthology.org/2026.acl-long.1394/ — factual retrieval is not person insight; evidence-linked temporal/causal reasoning remains much harder.
- Honcho benchmark discussion: https://honcho.dev/blog/blog/benchmarking-honcho — published recall benchmarks do not validate the marketed identity-modeling questions.

## Failure modes

- Product-wide shootouts when only one capability matters.
- Equal-weight scorecards that hide the actual user outcome.
- Rebuilding published benchmarks before checking existing evidence.
- Calling a candidate trial a comparison or architecture decision.
- Treating a generated profile as truth without source, temporal validity, or contradiction handling.
- Building background “deep insight” before showing one useful, evidence-grounded assistant behavior.