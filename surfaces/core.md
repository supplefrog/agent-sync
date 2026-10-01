# Shared instruction ownership

This file is a non-injected reference, not another prompt body. The effective host overlays are `recovery/current/hosts/hermes/SOUL.md` and `recovery/current/hosts/codex/AGENTS.md`; `contracts/instruction-surfaces.json` records where they actually load. Do not infer OMP inheritance from the Codex artifact's existence.

| Concern | Owner |
| --- | --- |
| Standing communication, judgment, artifact links, and orchestration consent | Host overlays; preserve necessary native differences |
| Model preferences and fresh reviewer dispatch | `surfaces/core.md`; host overlays load this owner before dispatch |
| Instruction content, triggers, sentence-level intent, and evaluation | `skills/skill-creator` |
| Automatic checked improvements from reusable workflows during work | `skills/skill-creator`; thin standing reminders in the effective host overlays |
| Unresolved Hermes placement | `skills/hermes-self-engineering` |
| Cross-host placement, parity, deployment, and recovery | `skills/cross-agent-surface-engineering` |
| Unresolved workflow design | `skills/outcome-first-workflow-design` |
| Starting, redirecting, or reviewing a project's architecture | `skills/project-prior-art` |
| Model-route research and qualification | `skills/openai-delegation-route-research` |
| Persisted DAG execution | `skills/dynamic-workflows` |

# Capability admission

Before installing, enabling, creating, replacing, retiring, or materially changing a shared agent capability or persistent behavior surface, use Agent Sync's `tools/reconcile.py` and the admitted `cross-agent-surface-engineering` owner. Existing admitted owners may be adopted or deployed only when deterministic checks prove a single-origin, reversible, non-conflicting change. Novel, staged, ambiguous, safety-sensitive, cross-host, or retirement changes require scoped authorization and recorded baseline/candidate evidence; they are not automatic promotions. Harness failure or missing evidence is inconclusive. Retaining the baseline is valid.

The staged `capability-curator` is not a promotion authority. Native local maintenance cannot admit, replace, or distribute portable capabilities. Project-local and ephemeral work is not promoted into shared ownership merely because an agent performed it.

# Execution contract

This is the single source of user model preferences and reviewer dispatch rules. Standing host instructions and memory point here; they do not maintain their own preference tables. Runtime settings and observed profiles record configuration, not preference authority. A newer explicit user instruction takes precedence; update this owner when asked to persist it.

## Model preferences

This block owns approved desired values. Native adapters read it; observations and running-session overrides remain separate. The Codex default follows the bounded-worker role, and the Hermes default follows its named role. Routine maintenance selects the maintained hosts; optional hosts retain their existing setup unless explicitly selected or required by a dependency. Supported default changes reconcile after scoped checks; they do not migrate running tasks or change provider/authentication.

<!-- agent-sync-preferences -->
```json
{
  "schema_version": 1,
  "roles": {
    "reviewer": {"model": "gpt-6.1-sol", "reasoning": "high"},
    "worker": {"model": "gpt-6.1-sol", "reasoning": "medium"},
    "linear": {"model": "gpt-6.1-sol", "reasoning": "high"},
    "hermes": {"model": "gpt-6.1-sol", "reasoning": "medium"}
  },
  "runtime_defaults": {"codex": "worker", "hermes": "hermes"},
  "maintained_hosts": ["codex", "hermes"],
  "optional_hosts": ["omp"]
}
```
<!-- /agent-sync-preferences -->

The current migration target is GPT-6.1 Sol for reasoning, planning, coding, design direction, and review. Do not introduce Astra, Fable, Kimi, or a cheaper reasoning tier unless the user selects one. Preserve each role's supported reasoning effort. Specialized embedding, transcription, rendering, and media-generation tools are capability dependencies, not reasoning-model preferences; check compatibility before proposing their replacement.

A user-authorized model migration includes the named legacy defaults, examples, workflow definitions, and resumable model pins, including historical configurations when selected. Update their executable model choices and any dependent identity/validation fields. Record what changed without claiming old executions used the replacement model. Generic preservation advice and superseded project prose cannot exempt an explicitly selected migration target.

## Dispatch and review

Use native bounded delegation when separate work or review materially improves the outcome. Use `dynamic-workflows` only for an explicitly selected routed contract or an existing pinned run. Preserve existing run pins unless the user's migration scope selects them for replacement; changing default preferences alone does not migrate running tasks.

When the user requests review, or nontrivial work makes difficult judgment, regression risk, or author bias material, spawn a fresh reviewer using the reviewer preference. Tiny unambiguous edits do not require a reviewer unless requested. Each review pass uses a new agent or session, not the author or a reused reviewer; in Codex use `fork_turns="none"` with explicit model and reasoning overrides. On other hosts use the supported fresh-child equivalent. Do not claim a fresh review if the host cannot provide one.

Give the reviewer a self-contained bounded handoff: intended and undesired outcomes, constraints and acceptance criteria, repository/artifact path, exact revision or patch identity, relevant evidence, and a read-only review scope. Let it inspect the artifact before the author's explanation; omit inherited conversation and other reviewers' verdicts. Request actionable findings with locations, evidence and remaining uncertainty. Shared models, instructions and tools still correlate errors; freshness alone is not proof of independence.

The parent checks findings against the current artifact, makes authorized fixes, and verifies acceptance. If a fix changes the reviewed concern, give a new reviewer the updated artifact for a bounded follow-up. Stop when criteria are met; no automatic fix-agent loops or expanding swarms. State desired and undesired outcomes and contraindications; leave methods open unless linear work benefits from steps.

Verify the requested model/reasoning and fresh-context controls are supported before dispatch. If unavailable, report the specific blocker; do not silently substitute a model or call self-review fresh review. Delegation adds no permission for paid inference, external or destructive actions, or approval bypasses. Parent acceptance, deployment and publication authority remain separate from reviewer findings.

## Discovery

Resolve the Agent Sync checkout from `source_snapshot` in the shared skill root's `.agent-signal-fleet.json`: strip the trailing `render/fleet` to get the checkout. Read this file before selecting a worker or reviewer. A missing contract is a dispatch blocker, not a reason to revive a remembered preference table.
