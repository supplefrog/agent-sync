# Agent Sync system requirements

Agreed project contract, 2026-09-27. This records expected outcomes, not a claim that they are implemented or an instruction to install a new governance framework.

Agent Sync assembles independently owned governance, authoring, reconciliation, and synchronization capabilities. Together they keep agents useful, consistent, and maintainable without requiring repeated audits of the complete setup. These requirements apply to skills, standing instructions, tool definitions and schemas, and their supported host adapters. Domain implementations retain their own owners.

## Owner map

Every expected behavior has one accountable owner. Supporting owners exchange evidence and artifacts rather than maintain competing policies. These roles should be apparent from the project entry point and implementation boundaries; the project may be reorganized for clarity. A rename is optional, not a prerequisite.

| Owner | Accountable outcome | Current places to inspect, not prescribed final structure |
| --- | --- | --- |
| Governance | Decide what belongs, what evidence permits a change, and whether the system improves user outcomes. | `contracts/ownership.json`, `registry.json`, `tools/capability_intake.py`, `skills/cross-agent-surface-engineering/` |
| Authoring | Improve the owning instruction or tool interface without losing useful behavior. | `skills/instruction-authoring/`; domain/tool owners for executable contracts; Codex native skill-creator for scaffolding/UI only |
| Reconciliation | Resolve differences and dependencies into a scoped, authorized change set. | `tools/reconcile.py`, `contracts/instruction-surfaces.json`, `contracts/surface-matrix.json` |
| Sync | Apply the selected changes, preserve recoverability, and verify the installed and published result. | `tools/fleet.py`, `tools/recovery.py`, `tools/sync_git.py`, host adapters |

These are responsibility boundaries, not requirements for four services, separate repositories, fixed folder names, or duplicated coordination layers. Existing combined modules can remain when their interfaces and responsibilities are clear.

## Expected outcomes

| ID | Accountable owner | Requirement |
| --- | --- | --- |
| R01 | Authoring | Each capability records the user's intention, distinguishes explicit intent from inference, and expresses its desired and undesired outcomes, relevant contraindications, and scope. Do not invent exclusions to fill a template. |
| R02 | Governance | Compare a candidate with the effective baseline: what improves, worsens, stays intact, and remains uncertain. Include useful quality, time, cost, and induced work; distinguish source/discovery checks from behavioral evidence. |
| R03 | Governance | Detect overlapping or conflicting capabilities and choose the correct owner. Preserve unique useful behaviors and necessary native differences rather than merging whole skills indiscriminately. |
| R04 | Authoring | Identify and repair scope creep, overly broad or missing triggers, and unnecessary skill/tool invocation within the owning capability. Check intended cases and nearby cases where it should stay inactive. |
| R05 | Authoring | Condense bodies and schemas by removing duplication, generic advice, stale rules, unnecessary fields, and excessive steering. Optimize useful loaded context and behavior, not word count alone. |
| R06 | Authoring | Present specific removal candidates, reasons, dependencies, and possible capability loss. Check callers and compatibility before removing schema/API fields; retain material exceptions and invariants. |
| R07 | Governance | Require evidence proportional to the change: intended behavior, nearby cases, regressions, and integrated acceptance. Use comparative checks when a quality benefit is uncertain; do not mistake artifact equality for behavioral parity. |
| R08 | Reconciliation | Carry changed user preferences through standing rules, owning skills, adapters, and tools without competing copies. Preserve existing pins unless changing them is authorized. |
| R09 | Authoring | Leave methods open where judgment helps; specify desired/undesired outcomes and real constraints. Preserve necessary safety, correctness, and verification procedures. Escalation follows the standing preference and the difficulty or judgment involved. |
| R10 | Sync | Verify what each affected host actually discovers, loads, and executes, including precedence, runtime support, tool capabilities, side effects, and failure behavior. Matching files alone is insufficient. |
| R11 | Reconciliation | Complete independently separable approved changes while leaving unrelated drift pending. Repository-wide visibility causes blocking only for a demonstrated dependency, conflict, or authorization boundary. |
| R12 | Sync | Preserve concurrent work, detect races, and support bounded retries, resumability, idempotence, and recoverable rollback. Reconciliation identifies dependencies; sync protects application and publication. |
| R13 | Governance | Maintain provenance, versions, evidence freshness, supersession, retirement decisions, and pending work. Staleness can trigger inspection; age or usage alone does not authorize removal. |
| R14 | Governance | Prefer the simplest method that meets the recorded intention at the required quality. Tools, workflows, and governance must justify their total cost through better outcomes or less total work; use adequate evidence without adding a comparison ritual when the choice is already clear. Avoid unnecessary reviews, experiments, repeated approval prompts, audit noise, latency, and instruction bloat. |
| R15 | Governance | Preserve scope, authorization, privacy, and native safety boundaries. Governance adds no permission for paid inference, external actions, destructive changes, credential access, or publication. |
| R16 | Sync | Report drafted, checked, locally deployed, and remotely synchronized states distinctly, with evidence and unresolved work. Do not call a partial result completed sync. |
| R17 | Governance | Reuse source-linked evidence bound to the relevant source/runtime identities. Inspect the changed owner and affected neighbors; broaden only when dependencies, conflicting evidence, or invalidated assumptions justify it. Support targeted revalidation so routine maintenance does not require another full-agent audit. |
| R18 | Governance | Make the owner map and requirement status apparent when opening the project. Map every expected behavior to its accountable owner, supporting interfaces, and relevant evidence; distinguish implemented, partial, missing, blocked, and unverified outcomes. |

Tool governance additionally considers schema clarity, parameter necessity, caller compatibility, side effects, errors, and supported execution boundaries. Governance decides whether a tool change meets the contract; the domain/tool owner remains responsible for its implementation. A smaller interface is not automatically a better interface.

## Desired result and limits

The system detects a concrete problem, routes it to the owner, develops and checks the smallest coherent correction, reconciles only the authorized dependencies, and verifies deployment. Existing/native solutions and no change remain valid choices.

Undesired outcomes include recurring complete-agent audits, a central policy monolith, duplicated owners, speculative capability claims, mechanical compression that loses knowledge, trigger overreach, scope creep, unrelated-work coupling, silent regressions, and governance whose overhead exceeds its benefit.

Contraindications include insufficient evidence for a claimed improvement, ambiguous ownership, inseparable conflicting edits, unsupported host mappings, incompatible schema callers, and actions beyond authorization. These conditions justify a specific pending decision or bounded investigation, not blanket blocking of independent approved work.

## Evidence status at preservation

The discussion observed competing Hermes defaults, canonical/live instruction drift, and unrelated dirty work blocking a scoped publication. Read-only inspection showed that the reconciler's plan describes metadata-only findings, while semantic scope/trigger/economy guidance exists in authoring skills and architecture prose. These observations motivate investigation; they do not establish that every requirement is missing, or that every problem remains present.

Implementation should distinguish existing guarantees from real gaps and preserve material uncertainty. Existing contracts, native capabilities, and useful safeguards remain constraints. The contract authorizes investigation and implementation through the main thread; it does not predetermine the mechanism or authorize unrelated changes.
