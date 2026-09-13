# Whole-system substrate evaluation

Use when a candidate is a complete agent harness, orchestration runtime, or trusted substrate rather than a detachable feature.

## Recover before redesigning

1. Search session history for prior inventories, architecture decisions, rejected alternatives, and artifact paths when the user indicates that work already exists.
2. Inspect the direct artifacts before relying on chat summaries, Kanban cards, memory, or reconstructed prose. These are views and may omit the decision core.
3. Reuse the prior inventory as evidence, but identify assumptions baked into its classifications and owner choices.
4. If the desired authority, interaction model, or substrate changed, reopen decisions whose conclusion depended on the old invariant. A framework rejected only because the incumbent was assumed canonical was not evaluated as a replacement.

## Discover adjacent products and protocols

1. Before limiting the evaluation to user-named contenders, run a concept-first blind search for systems that describe the desired interaction in outcome language. A close existing product discovered this way enters the intact-system lane even if the prior inventory omitted it.
2. Classify each discovery as a product, execution substrate, orchestration runtime, interaction protocol, executor, or adapter. Do not score a transport protocol as task authority unless it actually owns durable state, scheduling, recovery, side-effect semantics, security, and lineage.
3. Preserve specialist discoveries after selection when they solve a real layer cleanly. A candidate that fails standalone substrate gates may remain the best composer, protocol, executor, or product reference.
4. Stop adjacent discovery when another credible result cannot change the candidate set or the next highest-risk pilot.

## Evaluate intact before extracting

Treat state, execution, tools, security, recovery, interaction, and self-modification as a coupled system when their combination creates the value. Compare complete deployable stacks on the same user workflows. Do not begin with a portable-core/thin-adapter target and thereby make replacement candidates unable to win.

Keep **exploration, candidate comparison, provisional recommendation, and settled design** distinct. A user's shorthand for a possible hybrid (for example, combining two product names) is not evidence that the hybrid was designed or selected. Before describing a prior architecture, recover the exact proposal and decision evidence; label any new decomposition as current analysis rather than attributing it to the old thread.

Classify stack layers before recommending adoption: product/UI, agent harness, orchestration runtime, model/tool integration framework, execution backend, and optional hosted operations platform. Do not call a harness "the framework," treat a runtime as the agent, or imply that adopting one layer requires the vendor's full hosted stack. Explain each layer by the concrete failure or user outcome it owns.

Only extract after selecting a substrate, and only when a demonstrated missing capability has a stable boundary whose semantics survive separation. Prefer keeping another complete agent behind an executor, RPC, ACP, MCP, CLI, or sidecar boundary over copying its internals.

During intact evaluation, do not patch the contender to make a failed path pass. Record the intact failure first. A patched probe may later estimate repair cost, but label it separately and never use it as evidence that the upstream candidate passed.

## Capability inventory

Inventory **capabilities, not product names**. Before scoring contenders, normalize overlapping terminology into one row per user-visible outcome. A base shell and its extension distribution are one effective stack when the distribution is the shell plus extensions; do not count the shell again as an independent source of capability. Likewise, several agents exposing the same ordinary feature do not create several requirements or prove architectural breadth.

For each capability record:

- stable capability ID and user-visible outcome;
- interaction semantics and required invariants;
- every existing implementation that may satisfy it, with exact version/source;
- authoritative durable state and recovery behavior;
- model/executor/tool ownership and mutability;
- concurrent work, steering, interruption, cancellation, and status projection;
- intent, decision, provenance, and rejected-alternative lineage;
- sandbox, secrets, approvals, network, rollback, and irreversible-action boundary;
- UI/channel support and native/proprietary dependencies;
- host/platform constraints and verified local operation;
- extension surface and maintenance burden;
- evidence level for each implementation;
- best existing implementation, overlap, and integration cost;
- migration disposition: retain native, use intact executor/sidecar, port, rebuild, bridge temporarily, or drop.

Use this evidence order for material claims: user outcome → primary source → executable production-seam probe → durable receipt → comparison → independent challenge → disposition. Do not select an architecture merely by naming more agents or adding their feature lists together.

Do not collapse a capability into a black-box success/fail row. Verify the interaction and state transitions that produce the outcome. Separate agent/session lifecycle, delegated-task lifecycle, result delivery, artifact production, and model instruction-following; a single status or missing message does not prove all five failed.

When intent lineage is required, start with a generated, user-readable Markdown projection over canonical events. It may show desired outcome, current interpretation, constraints, decisions, superseded directions, open questions, commitments, and evidence. Do not create a second intent database or summarizer service until the projection demonstrably cannot satisfy the outcome.

## Disposition coverage and decision-package integrity

After selecting a substrate, create a machine-readable crosswalk from every recovered capability ID and every irreducible native-strength ID to one or more explicit `retain`, `port`, `rebuild`, `bridge`, or `drop` entries. Validate that the source and crosswalk ID sets are identical and that every referenced disposition exists. Aggregating a capability under a broader row is acceptable only when the crosswalk makes that relationship explicit; silent omission is not.

Before final handoff, validate the decision bundle as one release unit: every cited receipt exists; winner source/image identities agree across selection, build, and runtime evidence; disposition values and owner/null-owner invariants are valid; and all package files have a verified checksum manifest. Keep the checksum receipt outside its own hashed file set (or use a separately signed envelope) to avoid a circular manifest.

Normalize contender records before comparing them:

1. Require every intact contender—even one disqualified by a decisive failure—to answer the same fixed standalone-gate IDs and capability-contract IDs so retained strengths and untested gaps remain explicit.
2. Represent each assessment as `{level, finding}` and accept only the evaluation's declared evidence vocabulary. Reject undefined convenience labels such as `pilot_verified`; they conceal whether the user-facing path or only a subsystem ran.
3. Validate exact key equality, missing/extra criteria, and allowed levels programmatically across all candidates.
4. Apply levels conservatively: typed intent reconciliation is component evidence until natural-language interpretation and the final composer run; an offline evidence gate is not live research quality; one container does not prove every native executor's sandbox; WSL execution is not the final Desktop path.

Normalization standardizes the questions and vocabulary. It must not upgrade evidence merely to make the matrix look symmetrical.

## Representative acceptance scenarios

At minimum exercise:

1. One composer receives intertwined new and existing work and separates/deduplicates it without user-managed cards or threads.
2. Multiple tasks run concurrently and expose plain-language status, progress, steering, pause/cancel, and genuine-decision interrupts in the same surface.
3. A corrected or evolving requirement remains attached to the right task across restart, compaction, and another conversation.
4. The system researches existing solutions before building and preserves evidence and rejected alternatives.
5. The agent creates or changes a tool/runtime component, observes the result, and safely promotes or rolls it back.
6. Secrets and protected substrate remain inaccessible while legitimate work remains possible.
7. A native/proprietary capability is inventoried by behavior and either retained behind a boundary or explicitly accepted as a gap.

## Evidence and stopping

Use official source/docs plus real local builds or pilots. Classify every material claim as:

- **end-to-end verified** — observed through the real user-to-runtime-to-artifact path with a durable receipt;
- **component verified** — an implementation contract or subsystem test ran, but does not prove the user outcome;
- **documented** — supported by current authoritative source but not exercised here;
- **failed** — the real path was attempted and did not deliver the contract;
- **absent** — no supported path exists in the inspected current source.

Do not turn component tests into product claims. A whole-system contender is excluded only by a verified hard constraint or representative failure, not by ecosystem coupling, migration discomfort, or an incumbent-centric design preference. Separate **standalone gates** from ordinary capabilities: failing a gate disqualifies the candidate as sole substrate, but not necessarily as a composer, protocol, executor, or specialist layer.

Treat a leading contender as provisional until its highest-risk production seam passes. If an admitted worker can produce output yet fail to reach a durable terminal state or surface completion, do not rescue the substrate decision with prompt tuning, shutdown fallback, or a wrapper that invents success. Record the intact failure, preserve any non-authoritative executor value, and advance the next intact contender. The next contender may legitimately win by adding the smallest missing product layer—such as structural intent reconciliation over a checkpointed runtime—when that layer has one owner, durable persistence, executable tests, and no parallel ledger.

Separate runtime proof from model proof. A deterministic fake model can verify graph/checkpoint/fan-out/interrupt/dedup/restart semantics, but it does not verify natural-language intent classification, research quality, or provider behavior. Keep those as typed adapters with their own held-out evaluations. Conversely, a strong provider answer does not repair missing lifecycle or persistence contracts.

Separate self-modification proof by layer. A generated artifact or changed state field proves neither that the runtime consumed the change nor that promotion is safe. For bounded policy mutation, require approval, an allowlisted schema, base-version conflict detection, observation at the real consumer boundary, restart persistence, and idempotent conflict-safe rollback. Classify autonomous code/tool rewriting separately; it requires immutable build/promotion receipts and held-out behavior validation.

When validating replay or rollback, preserve the canonical head. Updating an old checkpoint in the same thread may make the branch the newest head even though the historical snapshot remains immutable. For user-facing alternatives, fork historical state into a separate deterministic thread/branch ID and verify both the branch and original canonical head after restart.

For an intact agent-stack evaluation, use this minimum evidence recipe:

1. Clone the canonical runtime/harness repositories into an isolated evaluation directory and record commit hashes, package versions, licenses, activity, and working-tree status. Check status before and after every build or probe. Do not install globally, change live configuration, or use credentials unless the user explicitly asks for a provider test.
2. Install into a private environment. Build one deterministic fake model and deterministic tools so runtime semantics can be tested without provider variance, then separately label provider-model behavior as unproven. If inherited host variables or plugins contaminate the environment, rerun through the project-local interpreter with only the contaminating inheritance removed; record both the harness problem and the isolated result.
3. Exercise a matrix rather than a hello-world: same-thread persistence, process restart/durable persistence, concurrent fan-out, nested subgraphs or subagents, streaming, interrupt/resume, state inspection, replay/fork/time travel, cancellation/error recovery, and one real API/UI surface.
4. Run the official local server/CLI when available. Validate its config, probe health/OpenAPI/thread/run/state endpoints, and visually inspect the rendered product surface. Capture startup warnings. Treat a local in-memory dev server as an API affordance, not production durability or security. If the server owns checkpointing, do not silently claim that a graph-level custom checkpointer is active; record the boundary and test the server-compatible graph separately.
5. Test target-platform boundaries through a live native adapter path, not only mocks or event translators. Include executable discovery and shim behavior, generated configuration/path serialization, process creation and termination, streaming, cancellation, credential-copy boundaries, and cleanup. A passing adapter unit suite does not prove that a real native executor starts or accepts generated configuration.
6. Map every claimed capability to an authoritative doc/repository citation and an observed command result. Keep source-supported, component-verified, end-to-end verified, hosted-only, failed, and not-exercised columns distinct.
7. Evaluate the conversational-OS outcome as a product interaction: one composer, automatic intent attach/split/supersede/dedup, multiplexed logical runs, merged event streams, approvals, identity/ACLs, cross-thread memory, auditability, sandbox/secret boundaries, rollback, and safe self-modification. Do not infer these from runtime primitives, injected prompts, or an exactly-once merge latch alone.
8. End with the smallest next pilot that closes the highest-risk gap, preferably a thin composer/API host over the intact contender with durable persistence and one approval flow, before adding broad integrations or polish.
9. Save machine-readable receipts with exact commands, commit IDs, evidence levels, and evidence paths. Validate that referenced files exist and that cleanup assertions match live state. Stop temporary servers, delete disposable sandboxes/probes, and restore only files the evaluation itself generated; never kill or revert a user process/file by inference.

Stop broad comparison after one contender satisfies required outcomes and credible alternatives are either exercised or excluded. Then produce the capability-by-capability migration plan and a working pilot before expanding polish.

## Session evidence that motivated this rule

A prior Hermes/Codex/OMP capability map and convergence contract existed under `{{agent-signal:HOME}}/Projects/agent-surface-bridge/`. It was useful inventory evidence but declared Hermes Kanban canonical, classified other systems as adapters, and treated LangGraph as task-local by construction. When the target changed to a single conversational OS with replaceable substrate authority, those owner conclusions had to be reopened while retaining the inventory itself.

A subsequent Prime pilot initially appeared to show a recursive worker producing the artifact while remaining `running` and withholding parent delivery. Re-analysis found multiple evaluator defects: formatting-specific JSON grep, an incomplete terminal-status vocabulary, and conflation of child/session lifecycle, delegated-task completion, result delivery, and model compliance. Current main still exposed only `queued → running` before shutdown, while an exact build of the active durable-terminal PR exposed `queued → running → done`; the latter still lacked the expected parent result notification in the exercised inline/RPC path. The valid conclusion is narrower: preserve these as separate lifecycle and delivery findings, test the exact open PR before duplicating it, and do not disqualify or promote the substrate until the production-seam contract is isolated. This is why evaluator validation belongs inside substrate evaluation rather than after the verdict.

The succeeding LangGraph + Deep Agents pilot remains useful component evidence: it kept model interpretation outside the proof boundary and verified structural mixed-turn reconciliation, turn-id idempotency, concurrent `Send` fan-out, evidence-gated research, supersession lineage, SQLite restart without rerunning terminal work, separate-thread historical fork, durable approval and `needs_review`/cancellation recovery, immutable source/image identity, and an offline non-root/read-only/no-network container. Its bounded self-modification probe changed the executor's actual concurrency configuration after approval, persisted across restart, and rolled back idempotently with version-conflict protection; it did not claim autonomous code rewriting. Treat that as a verified baseline, not an irreversible substrate decision when a newly released contender or corrected rival evidence can change the comparison.
