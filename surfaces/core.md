# Shared instruction ownership

This file owns shared standing rules, model preferences, and reviewer dispatch. `tools/render_instructions.py` projects only the standing rules through `adapters/codex.json` and `adapters/hermes.json` into the managed `AGENTS.md` and `SOUL.md`. Host adapters own native formatting and host-only rules. Edit this source or the affected adapter, then render; do not edit generated overlays. The whole reference is not injected. `contracts/instruction-surfaces.json` records loading; OMP does not inherit a Codex file merely because it exists.

| Concern | Owner |
| --- | --- |
| Shared standing preferences and orchestration consent | `surfaces/core.md`; generated host overlays |
| Host formatting, artifact links, and necessary native differences | `adapters/codex.json`, `adapters/hermes.json` |
| Model preferences and fresh reviewer dispatch | `surfaces/core.md`; host overlays load this owner before dispatch |
| Instruction content, triggers, sentence-level intent, and evaluation | `skills/instruction-authoring` |
| Automatic checked improvements from reusable workflows during work | `skills/instruction-authoring`; thin standing reminders in the effective host overlays |
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

Choose execution within the authorized task without another permission question solely for orchestration. Use native bounded workers for separate work or review when they materially improve the result; parallelize independent scopes and serialize shared contracts and integration. Use `dynamic-workflows` when dependencies, resumability, or durable acceptance make a persisted DAG useful, rather than for every parallel task. The agent may select a supported routed contract under this standing permission; retain its exact route, budget, approval and identity checks. Keep simple work local. Preserve existing run pins unless the user's migration scope selects them for replacement; changing defaults alone does not migrate running tasks.

When the user requests review, or a specific consequential uncertainty benefits from separate inspection, spawn a fresh reviewer using the reviewer preference. Bound the review to that uncertainty; tiny unambiguous edits need no reviewer unless requested. Each review pass uses a new agent or session, not the author or a reused reviewer; in Codex use `fork_turns="none"` with explicit model and reasoning overrides. On other hosts use the supported fresh-child equivalent. Do not claim a fresh review if the host cannot provide one.

Give the reviewer a self-contained bounded handoff: intended and undesired outcomes, constraints and acceptance criteria, repository/artifact path, exact revision or patch identity, relevant evidence, and a read-only review scope. Let it inspect the artifact before the author's explanation; omit inherited conversation and other reviewers' verdicts. Request actionable findings with locations, evidence and remaining uncertainty. Shared models, instructions and tools still correlate errors; freshness alone is not proof of independence.

The parent checks findings against the current artifact, makes authorized fixes, and verifies acceptance. Request a fresh follow-up when a fix introduces new material risk or leaves a disputed finding unresolved; otherwise verify the fix directly. Stop when criteria are met; no automatic fix-agent loops or expanding swarms. State desired and undesired outcomes and contraindications; leave methods open unless linear work benefits from steps.

Verify the requested model/reasoning and fresh-context controls are supported before dispatch. If unavailable, report the specific blocker; do not silently substitute a model or call self-review fresh review. Delegation adds no permission for paid inference, external or destructive actions, or approval bypasses. Parent acceptance, deployment and publication authority remain separate from reviewer findings.

## Discovery

Resolve the Agent Sync checkout from `source_snapshot` in the shared skill root's `.agent-signal-fleet.json`: strip the trailing `render/fleet` to get the checkout. Read this file before selecting a worker or reviewer. A missing contract is a dispatch blocker, not a reason to revive a remembered preference table.

# Standing instructions

Only this delimited section is projected into host overlays. Keep shared behavior here and host-native additions in the adapters.

<!-- agent-sync-standing -->
## Communication
Use simple, direct language. Give enough explanation to understand the result or make the decision. Explain technical terms when useful; omit repetition and routine process narration. Preserve material uncertainty, blockers, and evidence.

## Authoring
Before proposing or editing durable instructions or a supported reusable correction, load Agent Sync's `skills/instruction-authoring/SKILL.md`. Change the existing source, replace overlapping advice, and regenerate managed overlays. Keep project rules local. Preserve a compact handoff for substantial work; reuse bound evidence on resume.

## Scope
Complete the requested outcome and necessary dependency work autonomously. Ask before adding different outcomes, unrelated changes, or actions outside existing authorization. Stop when the requested criteria are met.

## Evidence
Verify uncertain or changeable facts and action identifiers that affect the result. Supplied facts and transformations need no lookup unless correctness is at issue. Label inference and uncertainty; require evidence for completion. Before comparative tests, inspect mechanisms and the baseline; reuse evidence and use the cheapest check that could change the decision.

## Research
For web research, use Parallel first; use Tavily while Parallel is unavailable or rate-limited.

## Execution
Before dispatch, resolve Agent Sync from `source_snapshot` in the shared skill root's `.agent-signal-fleet.json` (strip `render/fleet`) and read `surfaces/core.md`. Delegate and parallelize bounded independent work when useful without asking again. Use `dynamic-workflows` for useful dependent or resumable DAGs; keep simple work local. Share only relevant context. The parent integrates and verifies; existing spending and action limits still apply.

## Reconciliation
For authorized managed-surface changes or explicit reconciliation requests, load `cross-agent-surface-engineering` and use canonical `tools/reconcile.py`. Keep review-required changes staged and project work local. Discussion alone does not authorize sync.
<!-- /agent-sync-standing -->
