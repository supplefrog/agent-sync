---
name: hermes-self-engineering
description: "Use when changing or auditing Hermes behavior surfaces: skills, SOUL.md, agent.system_prompt/personality, provider request knobs, reasoning/display settings, auxiliary or delegation routing, memory, profiles, tools, or source. Select the narrowest owning surface, inspect current docs/source/config, test behavior before and after, and avoid prompt/config churn that makes a strong model worse."
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, self-engineering, prompt, config, skills, routing]
    related_skills: [hermes-agent, hermes-prompt-style-tuning, hermes-model-routing-evals, skill-creator]
---

# Hermes Self-Engineering

The goal is not to add instructions. It is to change the smallest surface that reliably changes the target behavior without degrading nearby behavior.

## 1. Define the target and failure

State in one sentence what should improve. Then identify:

- observed bad behavior and a representative prompt/reproduction;
- current owning surface candidates;
- evidence that would falsify each candidate;
- important nearby behaviors that must not regress.

For agent mistakes, distinguish missing instruction from bad trigger, instruction conflict, stale procedure, wrong tool/config surface, or failure to follow an already-correct rule.

## 2. Inspect the live system

- Load `hermes-agent` and use current official docs for supported behavior.
- Read the active config/home/profile and source path rather than assuming them.
- Search source before claiming a knob or hook exists.
- For provider/model behavior, verify live account availability and actual request acceptance.
- Search relevant session history when the change is meant to correct a repeated failure.

Do not treat a config write, accepted API field, or new skill text as proof behavior improved.

## 3. Choose the owning surface

Prefer the highest supported surface that directly controls the behavior:

1. **Provider-native request knob** — generation mechanics such as output verbosity, reasoning, service tier, JSON mode, or token limits.
2. **Task-specific auxiliary/delegation config** — cost, latency, and capability routing for a defined side task.
3. **Skill** — reusable task-class procedure, exact commands, local traps, scripts, templates, or references.
4. **`SOUL.md`** — durable identity, judgment, broad style, communication defaults, and standing behavior that should follow the Hermes instance everywhere.
5. **Optional `agent.system_prompt` / API override** — deployment-specific or experimental instruction text when no named personality is selected; it is appended at API-call time and should not be the default owner for baseline persona/communication.
6. **`/personality` / `agent.personalities`** — temporary or named persona overlays.
7. **Memory/user profile** — stable facts and preferences, not behavior procedures.
8. **Source/plugin** — only when supported surfaces cannot provide the behavior.

Use no durable change when the failure was one-off execution, incomplete evidence, or already prevented by existing instructions.

## 4. Check for negative steering

Before adding or preserving an instruction, ask:

- Does a capable current model already do this reliably?
- Is the rule compensating for an older/weaker model?
- Could a minimum-diff rule block a needed coherent fix?
- Could a mandatory plan, TDD, review, or subagent loop add more cost than confidence?
- Could a hard output cap suppress useful causal explanation?
- Does the trigger match too broad a task class?
- Is the content procedural knowledge, or stale provider/environment folklore?
- Does another skill already own the workflow?

Prefer deleting, merging, narrowing triggers, or moving details into on-demand references over adding another generic guardrail.

## 5. Make the change

- Keep prompt overlays short and positive.
- Keep skill descriptions precise about both trigger and exclusions.
- Put common workflow in one owner; use references instead of duplicating large sections.
- Preserve useful scripts/templates and hard-earned edge cases when consolidating.
- Do not edit other profiles unless explicitly requested.
- When supported configuration cannot fix the behavior, a tested source patch is allowed within the user's authorization. Preserve its source revision, exact diff, backup, rollback, and fresh-runtime checks. Public issues or pull requests are separate actions requiring their own authorization.

## 6. Verify behavior

Start with the cheapest acceptance probe, then scale:

- **Config/request knob:** read back config, verify backend acceptance, then behavior A/B.
- **Skill trigger:** test realistic positive and near-miss negative prompts.
- **Prompt/style:** compare answer quality, relevance, useful explanation, and bloat—not template compliance alone.
- **Model/routing:** use representative tasks, repeated calls, latency, errors/rate limits, token/tool usage, and externally verified outcomes.
- **Workflow change:** replay the failure class and inspect whether the new process prevents it without forcing unnecessary steps elsewhere.

Use `hermes-prompt-style-tuning` for style harnesses, `hermes-model-routing-evals` for provider/model benchmarks, and `skill-creator` when a skill genuinely needs formal trigger/output evaluation.

One small A/B is weak evidence. Apply broad defaults only when representative cases improve without meaningful regressions. For obvious redundancy/staleness, structural audit plus load verification may be enough; do not create expensive eval theater to prove identical duplicate text was removable.

## Intent-only autonomy and maintenance

When the target is "state the outcome and let Hermes handle the harness," treat this as a control-plane problem rather than another generic prompt rule:

- Keep one fixed daily-driver model for the user-facing conversation. Route work away from it only when task-class evidence justifies a cheaper worker or a stronger specialist.
- Do not map a single scalar complexity score directly to a model. Route on task shape, risk, expected duration, context needs, parallelizability, and how objectively the result can be verified.
- Choose execution shape automatically where supported: inline work, an isolated session, a persistent goal loop, a deterministic procedure, or durable multi-worker orchestration. Do not make the user classify the request first.
- Audit existing goals, delegation, Kanban, hooks, session overrides, background review, and curator behavior before inventing overlapping infrastructure.
- Govern impactful self-modification as: scout/research → evidence report → candidate change → disposable evaluation → user review → apply → post-apply smoke test/rollback. Automatic maintenance should be limited to clearly reversible housekeeping.
- Do not churn the main model, prompts, skills, or routing from trend reports alone. Challengers earn promotion through representative live-harness evaluation.
- Keep harness repair and upstream issue/PR handling inside the maintenance workflow; do not hand that operational burden back to a user who asked only for an outcome.

## Skill-library audit

When auditing persistence/workflows:

1. Inventory enabled skills, disabled list, categories, descriptions, linked files, and prompt-size contribution.
2. Name the problem each skill solves and whether that problem still exists.
3. Classify findings:
   - duplicate owner/trigger;
   - stale environment/provider/model assumptions;
   - over-procedural negative steering;
   - valuable specialized procedure/reference;
   - wrong persistence layer.
4. Consolidate only related workflows. Preserve domain skills whose procedures/scripts remain useful even if rarely triggered.
5. Prefer one concise umbrella with on-demand references to several overlapping prompt-heavy skills.
6. After changes, verify skills load, stale cross-references are gone, config-disabled names are sane, and prompt size moved in the expected direction.

## Reporting

Report:

- target behavior and chosen owner;
- what was added, removed, merged, or left unchanged;
- exact verification and before/after evidence;
- unresolved risk or restart/reset requirement.

## Pitfalls

- Display verbosity, reasoning visibility, reasoning effort, model output verbosity, and answer length are different controls.
- A model in a catalog may be unavailable to the account.
- Free-tier quality is irrelevant if live rate limits make it unusable.
- Do not store task results, run IDs, or short-lived provider rankings in memory.
- Do not patch the nearest loaded skill; patch the layer that owns the failure class.
