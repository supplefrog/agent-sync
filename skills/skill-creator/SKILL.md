---
name: skill-creator
description: Use when authoring instructions, reviewing model-facing tool interfaces, or preserving reusable workflows. Owns skill improvements during work, triggers, supporting resources, and proportional verification.
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [skills, instructions, evaluation, triggers]
    related_skills: [hermes-self-engineering, outcome-first-workflow-design]
---

# Skill Creator

Use this to author or review durable instructions and model-facing tool descriptions and schemas. Resolve placement only when it is unclear; this skill owns content, triggers, and proportional evaluation. Executable tool contracts and compatibility remain with their domain owner.

## Owner boundary

- Unresolved workflow/capability design => `outcome-first-workflow-design`; skip for a bounded wording, duplication, or stale-reference repair with a known owner.
- Cross-host placement or convergence => load `cross-agent-surface-engineering` first.
- Hermes behavior-surface ambiguity => load `hermes-self-engineering` first.
- Stable user/environment fact => memory, not a skill.
- Project-only convention => effective project context file, not a global skill.
- Repeated task procedure => one owning skill.

Patch an existing owner when it already covers the task. Create a new skill only when no owner can be extended coherently. Reference adjacent owners; do not copy their procedures.

## Improve skills during collaborative work

When the work establishes a reusable procedure, verified correction or explicit task-type preference, update its existing canonical skill during the work; do not wait for a separate save request or leave the only copy in a project diary. Review after a meaningful correction or verified flow and before closing substantial work, not after every tool call. Preserve task data and incident evidence locally.

Extract the reusable decision rule, its triggering conditions, and the nearby case it must not change. Project-specific taste and content stay in project context; a correction to the method belongs in the task's skill. Reconcile the rule with existing guidance rather than appending a competing instruction. If no durable lesson is supported or the owner already covers it, make no edit. Keep the standing trigger in the effective host instruction surface and the procedure here; verify that the trigger is available before the learning checkpoint, not only after this skill is manually loaded. Report checked source changes separately from live deployment; a blocked sync remains pending, not active across future threads.

Use the existing authorization for ordinary reversible skill improvements. Check the affected behavior and a nearby valid case, preserve rollback, and complete authorized synchronization. Do not duplicate an existing rule or create a new skill for a narrow addition. Speculative causal/model-quality claims remain candidates until suitable evidence supports them; automatic improvement is not automatic acceptance, paid evaluation, a new background watcher, or permission to weaken safeguards.

## Instruction modality

Choose form by behavior:

- Safety, governance, state, routing, verification => dense `condition => action` contracts with explicit boundaries and observable checks.
- Repeated deterministic work => concise procedure, decision rules, exact commands/scripts, failure handling, and verification.
- Creative, exploratory, research, strategy, synthesis => outcome, context, tensions, heuristics, and optional examples; preserve method freedom.
- Runtime/self-evolving capability => executable tools/policies and feedback; prose states intent and protected boundaries.

For mixed capabilities, separate protected invariants from judgment-bearing procedure. Leave methods open unless linear work benefits from steps; preserve required safety and verification procedures.

Write model-facing instructions in plain, human-readable language. Density should come from clear condition-to-action structure, not bureaucratic or generated-sounding phrasing. Do not route model-facing instructions through `humanizer`; this skill owns them, while `humanizer` owns public prose.

Apply the standing model preference to instruction writing according to the difficulty and judgment involved; trivial wording repairs do not automatically require escalation.

When writing durable instructions:

1. For each sentence, name the intended behavioral difference and its basis: user preference, required boundary, or observed failure. Remove generic identity/aspiration without a wanted distinction; do not invent a retrospective rationale. Test uncertain benefit rather than treating a plausible story as evidence.
2. State desired and undesired outcomes and contraindications directly. Preserve material exclusions while removing correction history, repetition, and incidental contrasts. Do not invent constraints or contraindications. Keep detail, examples, and rationale only when they change a decision or boundary.
3. Keep each procedure in one owner. Retain short, frequently needed rules inline when that avoids a larger skill load; defer substantial conditional detail. Judge economy by actually loaded context and induced tool work, not repository word count.
4. Preserve user intent, scope, safety, governance, authorization boundaries, and capability; approval for one task does not authorize adjacent external action; brevity never overrides these.
5. For retrying or externally mutating workflows, encode a stopping condition proportional to risk.
6. Narrow a rule to the failure's conditions before considering model-specific supplements. Keep one shared core unless a comparable baseline/candidate check shows a model needs a distinct rule. A model label or one incident is not that evidence.

## Skill structure

Every skill requires `SKILL.md` with YAML frontmatter:

- `name`: lowercase skill identifier, matching its folder.
- `description`: self-contained trigger and capability; put the discriminating trigger in the first 57 characters where practical.
- Optional metadata: version, author, license, platforms, tags, related skills, requirements.

Keep the entrypoint focused. Put substantial conditional detail in linked files:

- `references/` => schemas, APIs, policies, or mode-specific procedures.
- `scripts/` => deterministic repeated logic; execute it before promotion.
- `templates/` or `assets/` => artifacts used in outputs, not prompt prose.

Add a supporting file only when `SKILL.md` links it and names its trigger. Remove orphan examples, placeholders, copied manuals, and unused scaffolding.

## Optional review before editing

For persistent changes likely to cause ownership, overlap, catalog, or model-evidence rework, use the optional [authoring review](references/change-review.md). `tools/reconcile.py review` and `plan --target` share advisory checks; neither blocks ordinary editing nor grants publication permission. Small known-owner fixes can proceed directly.

When reusing or replacing an existing or native capability, consider the optional [useful-behavior review](references/useful-behaviors.md). Inspect the relevant procedures and explain omissions, alternatives, reasons and limits; a source reference can preserve a procedure without copying it.

For OpenAI model-specific prompt changes, use the installed OpenAI Docs procedure when available or current official model guidance otherwise. Bind comparisons to exact models and affected hosts. Structural checks and tool callability are not behavior measurements.

## Workflow

1. Inspect the current owner, neighboring owners, callers/references, and the observed failure or requested outcome.
2. State the target behavior and near-miss behavior that must remain unchanged. Check missing or overly broad triggers and unnecessary skill or tool invocation.
3. Draft the minimum coherent change using the correct modality. Condense duplicate advice, stale rules, excessive steering, and unnecessary fields while preserving material exceptions, side effects, error behavior, and execution boundaries. Before a removal, name the candidate, reason, dependencies, and possible capability loss; check callers and compatibility before removing schema or API fields.
4. Edit the canonical source; keep candidates outside live discovery until their checks pass. Use `skill_manage` only when it targets that source or performs authorized deployment.
5. Verify metadata/frontmatter, linked-file existence, and fresh skill discovery.
6. Run proportional behavior probes:
   - trigger change => realistic positive and near-miss prompts;
   - corrected failure => replay it plus one nearby valid case;
   - script/template => execute or render the real artifact path;
   - structural cleanup => load verification and stale-reference search may be enough.
7. Promote only when the candidate improves the target behavior without a material regression. Otherwise keep or restore the simpler baseline.

## Evaluation discipline

Do not force a fixed benchmark, subagent fan-out, viewer, exact wording assertion, or quantitative harness onto every skill edit.

Use baseline/candidate runs when model behavior or trigger selection is genuinely uncertain. Keep the model/runtime/tool context equivalent; native skill comparisons keep other catalog entries and tool access matched. Deterministic checks should enforce artifacts or true invariants, not paraphrasable prose. Use independent review only when complexity, risk, or author bias makes it materially useful.

Before spending inference on a workflow comparison, check whether the experiment can change the intended decision. Inspect the candidate's actual mechanism and the effective baseline first. Preserve normal discovery, available tools, and orchestration unless the question explicitly isolates a different variable; injected guides test injected guides, and a leaf worker cannot test a workflow whose mechanism requires independent workers. Reject an incompatible runner rather than silently simplifying the candidate.

Choose tasks that exercise the claimed advantage at the intended model's capability. Give product outcomes and necessary constraints, not the design, algorithm, or solution-order hints being evaluated. Keep those distinctions in parent-owned acceptance checks. For architecture, identify credible competing shapes and a follow-on change that could expose a bad choice; for reusable verification, measure subsequent use as well as creation. Synthetic cases remain useful for mechanism checks, not automatic evidence of workflow fitness.

Before candidate launch, record the adoption decision, mechanism-to-task fit, baseline fidelity, decisive checks, resource ceiling, and stop condition in the existing evaluation owner. Challenge the design for solution leakage, disabled mechanisms, and an obvious correctness ceiling; use a separate critique when substantial spend or author bias warrants it. A completed checklist is not proof of discrimination. Run only the cheapest runtime smoke needed for readiness, separately from quality trials. Match readiness checks to the intended action class; ordinary file writes or writable settings do not establish support for protected instruction writes. If these checks fail, repair the design before running or making comparative claims—not as caveats afterward.

Record only decision-changing evidence: prompt, active stack, catalog availability and verified skill-body reads, task outcome, verification, wall time, observed input/output tokens, and remaining uncertainty. Distinguish runtime readiness, task completion, and comparative quality; ties or passing structural checks establish no skill advantage. Measure governance overhead separately when it affects adoption; leave unobserved billed dollars null. Remove temporary eval sessions/workspaces after preserving required evidence unless the user asked to retain them.

## Completion

For approved changes owned by Agent Sync, finish the checked sync through `cross-agent-surface-engineering`, including local commit and remote push, as part of the same job unless the user requested draft-only or no publication. Do not leave routine commit/push steps for the user.

Report the selected owner, what was added/removed, verification results, and unresolved risk or restart requirement. If files changed, link the owning skill and any supporting artifacts.
