---
name: skill-creator
description: Use whenever creating, revising, auditing, or routing durable agent instructions or skills. Owns concise instruction authoring, placement handoff after hermes-self-engineering, trigger design, supporting resources, and proportional behavior evaluation.
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [skills, instructions, evaluation, triggers]
    related_skills: [hermes-self-engineering, outcome-first-workflow-design]
---

# Skill Creator

Author the smallest durable instruction set that changes the target behavior without constraining unrelated work. `hermes-self-engineering` selects the persistence surface; this skill owns skill and instruction content after placement is known.

## Owner boundary

- New or materially changed workflow/capability => load `outcome-first-workflow-design` before choosing a mechanism.
- Cross-host placement or convergence => load `cross-agent-surface-engineering` first.
- Hermes behavior-surface ambiguity => load `hermes-self-engineering` first.
- Stable user/environment fact => memory, not a skill.
- Project-only convention => effective project context file, not a global skill.
- Repeated task procedure => one owning skill.

Patch an existing owner when it already covers the task. Create a new skill only when no owner can be extended coherently. Reference adjacent owners; do not copy their procedures.

## Instruction modality

Choose form by behavior:

- Safety, governance, state, routing, verification => dense `condition => action` contracts with explicit boundaries and observable checks.
- Repeated deterministic work => concise procedure, decision rules, exact commands/scripts, failure handling, and verification.
- Creative, exploratory, research, strategy, synthesis => outcome, context, tensions, heuristics, and optional examples; preserve method freedom.
- Runtime/self-evolving capability => executable tools/policies and feedback; prose states intent and protected boundaries.

For mixed capabilities, separate protected invariants from judgment-bearing procedure.

Write model-facing instructions in plain, human-readable language. Density should come from clear condition-to-action structure, not bureaucratic or generated-sounding phrasing. Do not route model-facing instructions through `humanizer`; this skill owns them, while `humanizer` owns public prose.

When writing durable instructions:

1. Keep non-inferable requirements, invariants, decision rules, failure boundaries, and checks.
2. Reuse the established procedure for repetitive work.
3. Remove narrative, transitions, duplicated rules/conclusions, generic rationale, and examples that do not disambiguate.
4. State a reason only when omission could change implementation or hide a boundary.
5. Keep each rule in one owner; use a short routing trigger elsewhere when discovery needs help.
6. Preserve user intent, scope, safety, governance, authorization boundaries, and capability; approval for one task does not authorize adjacent external action; brevity never overrides these.
7. For retrying or externally mutating workflows, encode a stopping condition proportional to risk.
8. Do not turn one failure, model quirk, temporary route, or local incident into a universal rule.

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

## Workflow

1. Inspect the current owner, neighboring owners, callers/references, and the observed failure or requested outcome.
2. State the target behavior and near-miss behavior that must remain unchanged.
3. Draft the minimum coherent change using the correct modality.
4. Apply with `skill_manage`: `patch` for a narrow correction; `edit` for an intentional full rewrite; `create`/`delete` only with user authorization.
5. Verify metadata/frontmatter, linked-file existence, and fresh skill discovery.
6. Run proportional behavior probes:
   - trigger change => realistic positive and near-miss prompts;
   - corrected failure => replay it plus one nearby valid case;
   - script/template => execute or render the real artifact path;
   - structural cleanup => load verification and stale-reference search may be enough.
7. Promote only when the candidate improves the target behavior without a material regression. Otherwise keep or restore the simpler baseline.

## Evaluation discipline

Do not force a fixed benchmark, subagent fan-out, viewer, exact wording assertion, or quantitative harness onto every skill edit.

Use baseline/candidate runs when model behavior or trigger selection is genuinely uncertain. Keep the model/runtime/tool context equivalent. Deterministic checks should enforce artifacts or true invariants, not paraphrasable prose. Use independent review only when complexity, risk, or author bias makes it materially useful.

Record only decision-changing evidence: prompt, active stack, observable result, verification, and remaining uncertainty. Remove temporary eval sessions/workspaces after preserving required evidence unless the user asked to retain them.

## Completion

Report the selected owner, what was added/removed, verification results, and unresolved risk or restart requirement. If files changed, link the owning skill and any supporting artifacts.
