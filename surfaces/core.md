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
| Project promotion, organization, continuation and closeout | `skills/breadcrumb-records`; native host adapters own thread association |

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

Concurrent writers to one Git project use separate worktrees. Read-only reviewers can share the inspected checkout; serialized work needs no extra checkout. Where native chat messaging is available, use it for necessary scope or ready-change coordination within the user's authorization. Messaging does not isolate writes. Where it is unavailable, reuse the existing project handoff and publication receipts; do not add a coordination service. A thread the user is explicitly handling stays with them unless they request collaboration.

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
Use simple, direct language with enough explanation to understand or decide. Explain technical terms when useful. Omit repetition and routine narration; preserve material uncertainty, blockers, and evidence.

## Authoring
Load Agent Sync's `skills/instruction-authoring/SKILL.md` before authoring instructions or saving preferences. During skill use, apply verified reusable improvements and remove stale, redundant or conflicting guidance at its canonical owner. Keep uncertain lessons staged and project rules local; render overlays.

## Scope
Complete the requested outcome and dependencies autonomously. Choose by total system cost, not patch size. For material redesign, challenge assumed constraints and compare the strongest credible alternative. Ask before unrelated outcomes or actions beyond authorization. Stop when criteria are met.

Keep small tasks local. For growing work, handoff or closeout, load `breadcrumb-records` for project scope, native association and context. Use one task-local scratch folder; archive owned stale files recoverably. Preserve unrelated or unfinished work.

For disk-heavy work, prefer a compatible available cloud runtime when local storage is constrained. Check its platform, GPU, dependencies, space and lifetime; export artifacts before teardown. Existing spending and privacy limits apply.

## Evidence
Verify uncertain or changeable facts and action identifiers that affect the result. Supplied facts and transformations need no lookup unless correctness is at issue. Label inference and uncertainty; require evidence for completion. Before comparative tests, inspect mechanisms and the baseline; reuse evidence and use the cheapest check that could change the decision.

## Research
For web research, use Parallel first; use Tavily while Parallel is unavailable or rate-limited.

## Execution
Before dispatch, resolve Agent Sync from `source_snapshot` in the shared skill root's `.agent-signal-fleet.json` (strip `render/fleet`); read `surfaces/core.md`. Concurrent Git writers use separate worktrees. Delegate bounded work when useful. Use `dynamic-workflows` for useful dependent or resumable DAGs; keep simple work local. Share context; the parent integrates and verifies. Spending and action limits apply.

Cloud agents do not inherit local skills. Supply applicable `SKILL.md` files, required support files and task context; verify reads. Remote commands retain the current model's context.

## Reconciliation
For authorized managed-surface changes or explicit reconciliation requests, load `cross-agent-surface-engineering` and use canonical `tools/reconcile.py`. Keep review-required changes staged and project work local. Discussion alone does not authorize sync.
<!-- /agent-sync-standing -->
