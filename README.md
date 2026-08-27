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
- `evidence/` — public-safe findings and contradiction records.
- `tools/` — validation, evaluation, installation, and drift checks.
- `evals/` — reusable suites and compact result summaries; raw runs are ignored.
- `integrations/hermes/` — thin Hermes-native adapters for admitted event and lifecycle behavior.

The repository also contains a staged, read-only context-integrity ledger validation in `tools/context_ledger.py`. It stores provider-native identities plus source locators and digests—not transcript payloads—and keeps all provider mutations disabled. See `docs/context-integrity-ledger.md`.

The current local shared-memory decision keeps Hermes on tools-only Honcho, leaves Codex and OMP unmodified, and keeps `session_search` as the transcript-evidence path because no canonical provider passed admission. See `docs/shared-memory-decision.md`.

The event-driven Kanban caretaker lives in `integrations/hermes/kanban-caretaker/`. It uses native task lifecycle hooks for immediate blocked-task reconciliation and a script-only cron recovery scan, so a healthy board consumes no monitoring-model tokens. See `docs/kanban-caretaker.md`.

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

Ask for the behavior you want. `surface-convergence` maps it across agent modalities and hosts; `capability-curator` researches and admits any new or changed capability. Cross-host success requires current evidence on every required host. A host-native advantage or unsupported mapping remains an explicit delta rather than being hidden.

Broad instruction changes are gated by `tools/eval.py`, then aggregated with `tools/eval_gate.py`. Material work can additionally use `tools/grounded_gate.py` to freeze user-sourced criteria, separate intent/specification/test/implementation/oracle/verdict principals, require negative controls and teeth evidence, and prevent authors from certifying their own work. The evaluator runs matched repeated trials, deterministic hard checks, order-swapped blind judging, a bounded anytime-valid confidence rule, exact effective-stack fingerprints, and fresh session cleanup after a durable report. New v2 suites declare representative, near-miss, adversarial, and held-out cases. A timeout, interruption, judge failure, missing required host, or stack mismatch cannot promote or retire an instruction. Use `--retain-eval-sessions` only for explicit debugging evidence retention. See `docs/grounded-verification.md`.

`outcome-first-workflow-design` reconstructs why a workflow exists and compares retain/adapt/replace options before implementation. `openai-delegation-route-research` turns OpenAI release signals into evidence-gated speed- or intelligence-constrained delegation routes; when a changed stack is selected, `capability-curator` can run a bounded, cached bare/full/leave-one-out retirement pass instead of an expensive whole-library review. Hermes may schedule detection, but route and instruction promotion remain separate and never automatic.

You can invoke `/surface-convergence` or `/capability-curator` explicitly on hosts that expose skills as commands.

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
