# Architecture

## Product contract

Agent Signal accepts a desired persistent behavior and produces the smallest verified portable implementation:

1. compile the request into observable outcomes, triggers, regressions, target hosts, and acceptable deltas;
2. inventory the portable surface and each host's current native mechanisms;
3. research the baseline, canonical owner sources, and credible alternatives;
4. route persistent cross-agent changes through the admitted `cross-agent-surface-engineering` owner and deterministic `tools/reconcile.py` coordinator;
5. synchronize safe changes to existing admitted owners, while staging novel, unsafe, conflicting, retiring, multi-origin, or ambiguous work for separately evidenced review;
6. run baseline-versus-candidate, non-trigger, adversarial, and fresh held-out checks on every required current runtime;
7. preserve compact evidence, contradictions, hashes, versions, rollback, and reevaluation triggers; and
8. expose only admitted artifacts.

The convergence target is equivalent useful behavior. Mechanisms may differ, and valuable native capabilities remain native.

## Ownership layers

| Layer | Canonical artifact | Responsibility |
|---|---|---|
| Behavior contract | `contracts/surface-matrix.json` | Modalities, portable outcomes, host owners, support state, intentional deltas, evidence links |
| Portable procedures | `skills/` | Agent Skills-compatible workflows shared without host assumptions |
| Shared judgment surface | `surfaces/core.md` | Small, stable behavior and routing policy useful across hosts |
| Host integration | `adapters/` | Installation targets and discovery mechanisms only |
| Reconciliation and governance | `tools/reconcile.py`, `contracts/change-request.schema.json`, `reconciliation/requests/` | One deterministic inventory, classification, transaction, receipt, and rollback path used by all supported hosts |
| Host-native delta | `host-deltas.json`, `contracts/host-deltas.schema.json`, `tools/host_deltas.py` | Typed public-safe native state, restore prerequisites, source identity, version/hash, enablement, and readback |
| Cross-host routing | `skills/cross-agent-surface-engineering/` | Admitted judgment owner that routes persistent changes into the deterministic coordinator |
| Admission and retirement candidate | `skills/capability-curator/` | Staged evaluation artifact; not a live authority until separately admitted |
| Convergence candidate | `skills/surface-convergence/` | Staged evaluation artifact; not a live authority until separately admitted |
| Evaluation | `evals/`, `tools/eval.py`, `tools/eval_gate.py`, `tools/grounded_gate.py`, `tools/instruction_retirement.py` | Reproducible admission, independent grounded verdict contracts, and leave-one-unit-out comparison with artifact hashes and exact-stack receipt caching |
| Evidence memory | `evidence/findings.json`, `evals/results/` | Public-safe findings, contradictions, decisions, and compact summaries |
| Drift intake | `tools/capability_intake.py` | Read-only metadata scan across recovery and fleet state; classify owner, route, disposition, and bounded automatic eligibility without exposing file bodies |
| Drift and release | `tools/audit.py`, `tools/install.py` | Detect stale mappings and expose only admitted artifacts |

## Capability-librarian intake

`python tools/capability_intake.py scan --machine local-windows` composes the existing recovery dry-run and fleet planner. It reports only bounded metadata: surface, target identifier, current owner, route, change class, and review disposition. It has no apply command, does not read capability bodies into its report, and does not route live work through a staged owner.

This is the first vertical slice of the capability librarian, not autonomous promotion. A deterministic, reversible fleet action for an already admitted owner can be marked eligible only after checks. New or unmanaged capabilities, staged owners, content conflicts, retirement, recovery adoption, cross-host changes, safety-sensitive changes, and ambiguous changes remain review-only. Future Hermes or host hooks must remain thin adapters over this classifier and require separate admission evidence.

## Unified reconciliation

The phrase “reconcile with Agent Signal” is a shared, explicit ingress from Hermes, Codex, and OMP. Host instructions route it to admitted `cross-agent-surface-engineering`, which calls `tools/reconcile.py`; no host owns a competing governance receipt store.

The coordinator creates one bounded change request, inventories the canonical tree, rendered fleet, live managed state, recovery snapshot, and typed host deltas, then classifies the change before mutation. Its safe automatic cases are deliberately narrow:

- adopt a single-origin live change into the same existing admitted portable owner, then render, deploy, and verify it transactionally;
- deploy a canonical-only change for an existing admitted owner; or
- capture a reviewed allowlisted native change into recovery and the typed delta manifest.

The canonical source, rendered snapshot, live fleet, recovery snapshot, managed-state manifest, and request receipt are rolled back if a later transaction phase fails. A previously managed implementation is removed only when its identity still matches managed state and its replacement verifies. Novel capabilities, staged owners, multi-origin edits, conflicts, unsafe changes, removals/retirements, and ambiguous ownership cannot take the automatic path.

This provides a common sync operation, not universal interception. Manual editors and processes can still change files while no agent is running; an explicit host request or direct command performs the inventory and reconciliation. Project-local and ephemeral work is intentionally outside this system.

The effective governance authority is the deterministic contracts/coordinator plus admitted `cross-agent-surface-engineering`. The canonical `capability-curator` and `surface-convergence` designs remain staged until their own admission evidence is conclusive. The legacy Codex-only governance guard was retired after the common route and coordinator were installed.

### Scoped semantic curation

Keep useful knowledge discoverable, preserve meaningful triggers and procedures, and remove only what has stopped helping through recoverable changes. Reuse `skills/skill-creator` for semantic review and `cross-agent-surface-engineering` for ownership or deployment; no separate background semantic agent or new promotion authority is installed.

- Start from a concrete signal: a missed trigger, conflicting instructions, obsolete commands, demonstrated duplication, or an explicit user review request. Inspect only the affected owner and relevant neighbors. Usage and age can suggest inspection, never authorize retirement.
- Return retain, repair, merge, or retire with source evidence, the distinctions that must survive, and the smallest verification that could change the decision. Prefer no change when the existing owner already meets the need. A broad umbrella is not inherently better than distinct skills.
- The foreground parent owns ambiguous integration and acceptance of instruction changes; workers may collect evidence or propose edits. The current Hermes foreground is Astra. This is a responsibility boundary, not a model-specific tool sandbox or a claim that Astra has passed a comparative curator evaluation.
- Use direct checks for broken commands or links; realistic trigger and near-miss cases for discovery changes; comparative behavioral checks when benefit is uncertain. Reuse existing authorization and reconciliation gates rather than introducing another mandatory review hop. Keep removals recoverable and verify the actual target after applying a scoped change.

On the current Hermes installation, `curator.enabled: false` and `curator.consolidate: false` stop unattended lifecycle transitions and LLM rewriting. Native usage telemetry, inspection, pinning, and archive/restore facilities remain available; archiving is an explicit reviewed action, not a consequence of inactivity. The configured auxiliary curator model remains dormant while disabled. Do not run a whole-library consolidation pass as a substitute for semantic review.

The original `capability-curator` was included in Agent Signal's founding design. Its [cross-host admission report](../evals/results/capability-curator-cross-host-sol-ultra.json) is inconclusive with harness failures on both hosts; it is neither an admitted service nor evidence of general uselessness. Borrow its useful evidence principles through the existing owners, without activating the full staged procedure.

## Staged context-integrity validation

Cross-provider orchestration keeps transcript and task state in the native Hermes, Codex, and OMP owners; no single host board is the authority for every conversation or runtime. The staged `tools/context_ledger.py` prototype adds only provider-scoped execution identities, source locators/digests, versioned lineage and assertion evidence, and future receipt boundaries. It does not copy transcript payloads or enable provider mutations. See `docs/context-integrity-ledger.md` for the executable invariants and remaining admission gate.

## Recovery and instruction profiles

`recovery.json` allowlists public-safe declarative state and `tools/recovery.py` snapshots, diffs, merges, restores, and verifies it. `host-deltas.json` binds every reviewed native difference to its owner, desired state, source identity, version/hash, enablement, prerequisites, restore procedure, redaction policy, and readback. Admitted skills remain owned by the fleet; `bootstrap --apply` composes both paths and requires a clean postflight. Its report distinguishes `restored`, `verified`, `prerequisite-missing`, `excluded-private`, and `failed`. Credentials, memories, sessions, logs, caches, provider-hidden instructions, and runtime-generated environments remain outside the repository.

The recovery tests destroy temporary host roots and reconstruct allowlisted state plus the admitted fleet from the current repository snapshot, then require an exact second dry-run. This proves declarative reconstruction within the explicit boundary, not disk imaging: runtimes, authentication, private state, and unavailable native prerequisites must still be supplied externally.

`contracts/instruction-surfaces.json` inventories provider/runtime, global, project, inherited, hook-injected, disabled, and retired instruction surfaces. `contracts/instruction-units.json` makes effective generic steering independently retireable. A model profile binds the current model/provider/runtime/reasoning stack to exact user-owned artifacts and standing-byte budgets without pretending to copy provider-hidden system prompts.

## Retained native strengths

### Codex

- tree-scoped repository instructions through `AGENTS.md`;
- standard Agent Skills discovery and MCP support;
- host-native sandbox, approvals, managed policy, plugin, and execution controls;
- Codex-native planning and configuration behavior.

### Hermes

- first-class `SOUL.md` personality and session behavior;
- Agent Skills external directories and lifecycle tooling;
- broad native tools, MCP, plugins, hooks, approvals, safe mode, and redaction;
- delegation, model routing, memory, goals, cron, gateway delivery, and background execution.

The shared layer specifies outcomes. It does not emulate these mechanisms unless equivalence is reliable and useful.

## Model-triggered instruction retirement

Skills and global agent files are model inputs, not permanent capabilities. When a changed model stack is selected for an active route, Agent Signal performs a bounded inverse-admission pass:

1. remove deterministic duplicates and dead mappings without model calls;
2. reopen only model-sensitive generic steering, not stable commands, local procedures, or protected guarantees;
3. compare the bare model, the current full owner, and full-minus-one-unit on a compact owning suite plus canaries;
4. prefer deletion on a clean tie, use binary splitting only when overlapping units preserve a demonstrated gain, and escalate subjective judging only at the boundary; and
5. cache by the effective model/provider/reasoning/tool/prompt stack plus unit, suite, and harness hashes.

The release cron may produce a retirement plan and evidence only after recommending the model for an active route. It never edits live surfaces or runs the whole skill library through an LLM curator.

## Rejected patterns

- identical files as proof of behavioral parity;
- an ambient universal hook or watcher that neither host natively guarantees;
- synchronizing private memory, sessions, credentials, or raw transcripts;
- deleting a host advantage to reach a lowest common denominator;
- cloning staged skills into a live discovery directory;
- marketplace popularity or upstream benchmarks as local admission proof;
- fixed weak-worker routing for research, architecture, evaluation design, or synthesis;
- deleting contradictory evidence to make a release appear unified;
- copying canonical artifacts into divergent host stores.
- exhaustive per-line or whole-library LLM pruning after every model release.

## Current modality program

The matrix deliberately includes unassessed rows. A row advances only when its current-stage artifact, suite, and compact cross-host evidence exist.

1. **Foundation:** instructions, Agent Skills, admission, convergence, adapters, audit, and staged installation.
2. **Shared tools and routing:** MCP/tool contracts, delegation and model-routing semantics, policy and security boundaries.
3. **State and durable work:** memory/context privacy, plans, goals, schedulers, background work, and external automation.
4. **Additional agents:** map a new host into existing modality contracts, add only required adapters, and extend the cross-host rows.
5. **Public release:** current evidence on every required host, public-path scan, clean clone install/doctor, rollback exercise, and remote publication.

Partial support is a valid staged result. It must remain explicit and cannot be marketed as confirmed convergence.

## Version anchors for the current comparison

- Agent Skills specification: <https://agentskills.io/specification>
- Codex source/docs revision: `985641272869835d01d025ed2a218fbbce35fa9f`; local CLI `0.153.1`
- Hermes upstream revision: `63279301bcbdc185c1b07b98a9312eb0c862f26d`; local CLI `0.21.0`
- OMP release revision: `v17.2.13`; local CLI `17.2.13`
- Codex instruction docs: <https://github.com/openai/codex/blob/985641272869835d01d025ed2a218fbbce35fa9f/docs/agents_md.md>
- Codex skill docs: <https://github.com/openai/codex/blob/985641272869835d01d025ed2a218fbbce35fa9f/docs/skills.md>
- Hermes configuration docs: <https://hermes-agent.nousresearch.com/docs/user-guide/configuration>
- Hermes skills docs: <https://hermes-agent.nousresearch.com/docs/user-guide/features/skills>

These anchors establish what was inspected, not permanent truth. Relevant host or artifact changes stale only the affected evidence rows.
