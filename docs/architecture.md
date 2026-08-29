# Architecture

## Product contract

Agent Signal accepts a desired persistent behavior and produces the smallest verified portable implementation:

1. compile the request into observable outcomes, triggers, regressions, target hosts, and acceptable deltas;
2. inventory the portable surface and each host's current native mechanisms;
3. research the baseline, canonical owner sources, and credible alternatives;
4. use `capability-curator` to stage and qualify any new or changed capability, and to retire generic steering that no longer beats the current model baseline;
5. map the admitted behavior through `surface-convergence` into one portable contract plus thin host adapters;
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
| Admission and retirement | `skills/capability-curator/` | Research, qualify, adapt, compare, reject/admit capabilities, and run bounded instruction retirement after model changes |
| Convergence | `skills/surface-convergence/` | Map admitted behavior across hosts and manage semantic delta |
| Evaluation | `evals/`, `tools/eval.py`, `tools/eval_gate.py`, `tools/grounded_gate.py`, `tools/instruction_retirement.py` | Reproducible admission, independent grounded verdict contracts, and leave-one-unit-out comparison with artifact hashes and exact-stack receipt caching |
| Evidence memory | `evidence/findings.json`, `evals/results/` | Public-safe findings, contradictions, decisions, and compact summaries |
| Drift and release | `tools/audit.py`, `tools/install.py` | Detect stale mappings and expose only admitted artifacts |

## Staged context-integrity validation

Cross-provider orchestration keeps transcript and task state in the native Hermes, Codex, and OMP owners; no single host board is the authority for every conversation or runtime. The staged `tools/context_ledger.py` prototype adds only provider-scoped execution identities, source locators/digests, versioned lineage and assertion evidence, and future receipt boundaries. It does not copy transcript payloads or enable provider mutations. See `docs/context-integrity-ledger.md` for the executable invariants and remaining admission gate.

## Recovery and instruction profiles

`recovery.json` allowlists public-safe declarative state and `tools/recovery.py` snapshots, diffs, merges, restores, and verifies it. Admitted skills remain owned by the fleet; `bootstrap --apply` composes both paths and requires a clean postflight. Credentials, memories, sessions, logs, caches, and runtime-generated environments remain outside the repository.

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
- a universal hook or memory schema that neither host natively guarantees;
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
- Codex source/docs revision: `a9802304f60ab14c0b07e3ee0db9a9c105ab0cb3`; local CLI `0.150.0-alpha.12.2`
- Hermes upstream revision: `933c209e96630a6026b0a18ecf6a86e65110f5b8`; local CLI `0.20.5`
- Codex instruction docs: <https://github.com/openai/codex/blob/a9802304f60ab14c0b07e3ee0db9a9c105ab0cb3/docs/agents_md.md>
- Codex skill docs: <https://github.com/openai/codex/blob/a9802304f60ab14c0b07e3ee0db9a9c105ab0cb3/docs/skills.md>
- Hermes configuration docs: <https://hermes-agent.nousresearch.com/docs/user-guide/configuration>
- Hermes skills docs: <https://hermes-agent.nousresearch.com/docs/user-guide/features/skills>

These anchors establish what was inspected, not permanent truth. Relevant host or artifact changes stale only the affected evidence rows.
