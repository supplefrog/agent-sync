# Agent Signal

A portable agent surface that turns “I want X behavior” into researched, tested, cross-host capability.

## Why

Agent Signal compares the best native and portable mechanisms instead of forcing every agent into one implementation. A behavior is published only after the system:

1. compiles the request into an observable behavior contract;
2. inventories the current Codex, Hermes, and portable surfaces;
3. researches canonical implementations and credible alternatives;
4. stages and tests the smallest candidate on every required current runtime;
5. rejects capability regressions and false parity; and
6. preserves compact findings, contradictions, intentional deltas, and reevaluation triggers.

The target is semantic parity with useful native differences—not identical files, lowest-common-denominator behavior, or a universal hook abstraction. Host lifecycle tools remain useful after admission for staleness, merging, and pruning.

## Layout

- `skills/` — portable [Agent Skills](https://agentskills.io) source of truth.
- `surfaces/core.md` — shared global behavior for supported agents.
- `adapters/` — thin declarative host installation and discovery mappings.
- `contracts/` — canonical modality contracts, host mappings, and intentional deltas.
- `profiles/` — model/provider/runtime-qualified standing-instruction profiles and context budgets.
- `recovery/` — reviewed public-safe declarative state snapshots; never raw agent homes.
- `reconciliation/` — bounded change-request receipts and dispositions from the shared sync workflow.
- `host-deltas.json` — typed, public-safe host-native state and recovery requirements.
- `evidence/` — public-safe findings and contradiction records.
- `tools/` — validation, evaluation, installation, and drift checks.
- `evals/` — reusable suites and compact result summaries; raw runs are ignored.
- `integrations/hermes/` — thin Hermes-native adapters for admitted event and lifecycle behavior.

The repository also contains a staged, read-only context-integrity ledger validation in `tools/context_ledger.py`. It stores provider-native identities plus source locators and digests—not transcript payloads—and keeps all provider mutations disabled. See `docs/context-integrity-ledger.md`.

The current local memory decision keeps Hermes on compact built-in memory, authoritative artifacts, skills, and exact session retrieval; external providers are retired because no repeatable external-only downstream win was observed. Codex and OMP remain unmodified. See `docs/shared-memory-decision.md`.

## Canonical ownership

`contracts/ownership.json` names one portable owner for every registered capability and the exact supported host roster: Hermes, Codex, and OMP. Host integrations may adapt a canonical capability, but may not publish a competing `SKILL.md` or own portable workflow state. The repository audit fails on unregistered skills, duplicate integration entrypoints, unsupported adapters, ownership/registry drift, or the reappearance of a retired artifact.

`skills/dynamic-workflows/` is the definitive routed-DAG owner. Codex, Hermes, and OMP use thin native adapters; Hermes exposes persisted DAG execution through `routed_workflow` while ordinary one-shot routed children remain on `routed_delegate_task`. No adapter owns a second workflow state machine.

## Fleet render and sync

`fleet.json` is the machine inventory. The fleet tool renders only admitted
skills, previews changes, applies them without touching unrelated host skills,
and verifies both installed content and its managed-state manifest:

```bash
python tools/fleet.py render
python tools/fleet.py diff
python tools/fleet.py apply
python tools/fleet.py verify
```

The current `local-windows` machine exposes one shared Agent Skills root to
Hermes, Codex, and OMP. Host-specific instruction and runtime adapters remain
owned by `adapters/`; the fleet tool does not flatten intentional host deltas
into identical files. A same-name unmanaged skill or a locally modified managed
skill fails closed. Retired skills are removed only when their installed bytes
still match the previous fleet state. Generated snapshots live under
`render/fleet/` and are not committed.

See `docs/fleet.md` for the state and failure contract.

## Unified reconciliation

“Reconcile with Agent Signal” is the common ingress from Hermes, Codex, and OMP for persistent agent changes. Each host routes the request to the admitted `cross-agent-surface-engineering` owner, which invokes the same deterministic coordinator:

```bash
python tools/reconcile.py plan
python tools/reconcile.py sync --adopt <admitted-owner>
python tools/reconcile.py sync --capture-recovery
```

The coordinator inventories canonical, rendered, live-fleet, recovery, and typed host-delta state before changing anything. `sync` is one complete job: validate the intended changes, share them with the appropriate agents, commit locally, push to the existing upstream branch, and read back that branch before reporting success. Native settings remain host-specific. No force-push, automatic promotion of staged skills, or blind `git add .` is allowed.

The agent reviews additional repository edits and passes their exact filenames using repeated `--include FILE` arguments; the user need not manage separate commit/push steps. Missing ownership, conflicting edits, retirements, unsafe content, or unknown publication scope stop for review. A failed commit or push reports `incomplete` and retains a private pending record under `.git`; rerunning sync resumes the same checked changes instead of creating duplicate commits. A local fleet update or saved settings file alone is not a completed sync. Low-level `fleet.py apply` and the Python `sync()` helper remain available for tests/maintenance but do not claim publication.

Novel capabilities, staged owners, conflicting or multi-origin edits, unsafe changes, removals/retirements, and ambiguous ownership remain review-only or rejected. Project-local and ephemeral work stays local. This is an explicit sync workflow, not an ambient filesystem watcher: out-of-band changes are reconciled when a host receives the phrase above or an operator runs the command directly.

The live authority is the deterministic Agent Signal contracts/coordinator plus admitted `cross-agent-surface-engineering`. The staged `capability-curator` and `surface-convergence` candidates are not live authorities and cannot promote themselves. [Scoped semantic curation](docs/architecture.md#scoped-semantic-curation) reuses the admitted instruction-review and ownership workflows. Hermes automatic curation is disabled on the current installation; native telemetry and manual recovery remain available, but inactivity alone does not authorize archiving. The former Codex-only governance guard has been retired after the shared route and coordinator replaced it.

## Public-safe recovery

Agent Signal also restores the current allowlisted Hermes, Codex, and OMP settings,
global instruction files, user-authored hooks, public plugin selections, credential-free
MCP declarations, thin adapters, and admitted portable skills. `host-deltas.json` records
the typed native differences, their prerequisites, source identities, hashes/versions,
restore procedures, and readback checks.
It excludes credentials, auth, memories, sessions, logs, caches, volatile runtime
environments, and generated artifacts.

```bash
python tools/recovery.py verify
python tools/recovery.py bootstrap          # dry-run
python tools/recovery.py bootstrap --apply  # restore + full postflight
```

Config restore merges only explicit allowlisted paths and preserves unknown or
sensitive fields already present. Differing text artifacts fail closed unless the
operator explicitly supplies `--force-text`. The state report distinguishes
`restored`, `verified`, `prerequisite-missing`, `excluded-private`, and `failed`.
See `docs/recovery.md`.

Classify recovery and fleet drift without mutating either surface:

```bash
python tools/capability_intake.py scan --machine local-windows
```

The scanner reports bounded metadata and review routes only. Novel, staged,
conflicting, cross-host, safety-sensitive, and ambiguous changes are never marked
for automatic application. See `docs/architecture.md`.

The current `gpt-6-astra` / `openai-codex` user-owned instruction overlay is
identified by host, runtime, reasoning level, artifact hash, effective unit, and
standing byte budget in `profiles/gpt-6-astra-openai-codex.json`. Provider-hidden
and runtime-native system instructions are inventoried as external dependencies,
not copied or guessed. See `docs/instruction-profiles.md`.

## Legacy installer

Clone outside an agent's live skill-discovery directory, then run:

```bash
python tools/install.py
```

Do not clone the repository directly into `~/.agents`: Codex treats `~/.agents/skills` as live user skills, which activates staged candidates and contaminates baseline evaluations. The legacy installer exposes each admitted skill individually and preserves unrelated skills; the fleet path above is the normal distribution route.

The older installer remains available for link-based development and Hermes
discovery configuration. Normal distribution should use `tools/fleet.py`, which
installs rendered copies and records managed state instead of keeping live
runtime directories coupled to the working tree.

Verify:

```bash
python tools/install.py doctor
python tools/validate.py
```

## Use

Ask for the behavior you want. For a persistent agent change, say “reconcile with Agent Signal”; Hermes, Codex, and OMP route that request through the same admitted cross-agent owner and deterministic coordinator. Existing admitted owners can be synchronized under the bounded automatic rules above. New, conflicting, unsafe, or ambiguous capabilities are staged for evidence-backed review rather than silently promoted. Cross-host success requires current evidence on every required host, and a useful host-native advantage remains a typed delta rather than being flattened or hidden.

Broad instruction changes are gated by `tools/eval.py`, then aggregated with `tools/eval_gate.py`. Material work can additionally use `tools/grounded_gate.py` to freeze user-sourced criteria, separate intent/specification/test/implementation/oracle/verdict principals, require negative controls and teeth evidence, and prevent authors from certifying their own work. The evaluator runs matched repeated trials, deterministic hard checks, order-swapped blind judging, a bounded anytime-valid confidence rule, exact effective-stack fingerprints, and fresh session cleanup after a durable report. New v2 suites declare representative, near-miss, adversarial, and held-out cases. A timeout, interruption, judge failure, missing required host, or stack mismatch cannot promote or retire an instruction. Use `--retain-eval-sessions` only for explicit debugging evidence retention. See `docs/grounded-verification.md`.

`outcome-first-workflow-design` reconstructs why a workflow exists and compares retain/adapt/replace options before implementation. `openai-delegation-route-research` turns OpenAI release signals into evidence-gated speed- or intelligence-constrained delegation routes. A future admitted curator may run bounded, cached bare/full/leave-one-out retirement passes after a model change; the current staged `capability-curator` does not participate in live admission. Hermes may schedule detection, but route and instruction promotion remain separate and never automatic.

The staged `/surface-convergence` and `/capability-curator` candidates are evaluation artifacts, not deployed commands or authorities.

See `docs/architecture.md` for the end-to-end system and `docs/modality-research.md` for the current comparison and staged evaluation program.

## Design choices

- **Primary-source-first:** catalogs, posts, and videos are leads; claims are traced upstream to owner docs, source, releases, tests, or papers.
- **Precision over coverage:** at most three finalists; no install is a valid outcome.
- **Live proof:** popularity and upstream evals are evidence about provenance, not proof of fit for your model.
- **One canonical tree:** compatible agents read the same `skills/` directory instead of copied skill stores.
- **Thin adapters:** host-specific hooks are optional. The portable skill and evidence contract stay authoritative.
- **Evidence memory:** useful negative findings and contradictions survive without publishing transcripts, private paths, or user memory.
- **Version-bounded claims:** a host, model, tool, artifact, or upstream change can stale only the affected evidence.

## License

MIT. Third-party candidates are not republished unless their licenses permit it; provenance must be retained in each admitted skill.
