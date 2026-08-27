---
name: outcome-first-workflow-design
description: Use when creating or materially iterating an agent workflow, automation, reusable procedure, or persistent capability. Reconstruct the user's intended outcome, inspect why the current mechanism exists, research supported existing solutions, and compare retain/adapt/replace options from first principles before building.
license: MIT
compatibility: Requires access to the current artifact and, when external options matter, source or web research.
metadata:
  author: supplefrog
  version: "0.1.0"
---

# Outcome-First Workflow Design

Use this before creating or materially changing a workflow, automation, reusable procedure, or persistent agent behavior. It owns intent reconstruction and solution choice; implementation-specific skills own execution.

## Contract

Optimize the user's outcome, not fidelity to the mechanism they named. Treat the request as partial evidence: reconstruct the likely goal, challenge weak mechanism assumptions, inspect what already exists, and proceed on supported reversible defaults. Preserve explicit constraints and safety boundaries. A better result may be to reuse, simplify, adapt, replace, or make no change.

## Procedure

### 1. Reconstruct intent and recover evidence

Before generating options or mechanisms, inventory the evidence that already exists: the user's supplied material, prior research and decisions, current artifact and neighboring callers, documentation, tests, evaluations, history, and relevant session records. Reuse verified findings rather than restarting discovery; mark stale, conflicting, or missing evidence explicitly. Separate the desired outcome, trigger, success measures, failure cost, explicit constraints, incidental implementation choices, and guarantees the current design may protect. Mark evidence, inference, and unresolved ambiguity. Do not turn missing detail into an intake interview: infer from evidence, state consequential assumptions, and start useful discovery or implementation. Ask only when the remaining ambiguity would materially change the product and cannot be resolved by evidence because it depends on a user-owned value or hard-to-reverse commitment. New research begins only for gaps that could change the decision.

### 2. Describe the outcome contract

Before choosing a mechanism, state observable triggers, measurable results, hard failures, non-goals, cost/latency/maintenance/privacy/reversibility bounds, and checks that would prove the result. Prefer pass probability, latency budget, or recovery guarantees over labels such as simple, smart, fast, or robust.

### 3. Inspect baseline and rationale

Trace the live implementation end to end. For existing workflows, inspect source history or decision records when available. Identify what is already solved, what is load-bearing, and the exact mechanism where the claimed gap appears. Stop when the baseline already meets the outcome and another layer would add only overlap or ceremony.

### 4. Research only decision-changing gaps

Audit enabled skills and host-native capabilities before launching a new workflow; if an existing owner already satisfies the outcome, route to it rather than duplicating its procedure. Search externally only for unresolved gaps that could change the decision. For technical solution discovery, load `iterative-blind-research` and complete its GitHub-first implementation sweep before moving to papers or inventing a new mechanism; use `external-skill-intake` when an outside skill may be adopted. Compare reference architectures, comparable projects, frameworks, owner docs/source/releases/tests/specifications, maintained standards, and reproducible practitioner evidence. Use `advise-project-approach` when an established project approach may fit. Use `neuroarxiv` only when recovered evidence and ordinary implementation research leave a genuinely new project-architecture question. Compare at most three credible finalists and include retain/simplify.

### 5. Decide from first principles

For each candidate, explain the mechanism that could satisfy the outcome. Compare only decision-changing dimensions: verified task success, failure behavior, latency, total expected cost including retries/verification, compatibility, security, maintenance, and rollback. Apply hard constraints before Pareto comparison. Prefer the simpler reversible option when differences are within uncertainty.

### 6. Keep material decisions traceable

Externalize the decision path while work is live so later context loss cannot turn an assumption into an unexplained architecture:

- Record the outcome, material constraints, evidence, live alternatives, recommendation, decisive tradeoff, assumptions, and the condition that would reopen the choice. Reuse the project's existing plan or ADR owner; otherwise keep the compact trace in the handoff instead of inventing a new ledger format.
- When the current architecture already fixes the choice, or evidence supports a reversible default, record that basis and proceed without reopening design.
- When evidence supports one option, present that recommendation and proceed within the user's authorized scope; do not convert option comparison into a questionnaire.
- Stop only before implementing a choice that is both material and hard to reverse and remains undecidable after evidence because alternatives encode different user values. Present the recommendation and the smallest unresolved branch, then request selection or approval of that branch—not a general interview.
- Do not let workers choose an unresolved material architecture implicitly. Fix shared contracts before fan-out, then let independent work run in parallel only where ownership and dependencies do not collide.
- Treat unresolved, blocked, or abandoned branches as first-class outcomes with reasons and impact. Never hide them in a completion summary.

This section owns decision authority and traceability, not execution machinery. Reuse existing task decomposition, scheduling, acceptance-gate, and worker-lifecycle owners; do not copy another workflow's tree, depth ritual, checker, lease, or scheduler.

### 7. Validate before promotion

Stage outside live discovery and shared config. Translate the outcome into observable acceptance checks before implementation; make checks runnable against the resulting artifact where possible. Exercise representative, adversarial, non-trigger, and held-out cases. Verify returned work and consequential claims independently of agent self-report, rerunning checks at the parent boundary when work was delegated. Promote only a coherent winner that beats or necessarily restores the baseline without a material regression. Record evidence, unresolved checks, rollback, and reevaluation triggers.

## Output

Return the decision, intended outcome, decisive evidence, chosen mechanism, validation, and remaining uncertainty. Exclude research narration and implementation work that cannot change the decision.

## Failure modes

- building the named mechanism before establishing the outcome;
- stopping ordinary work for a fixed intake questionnaire when evidence or a reversible default can decide;
- presenting options without a supported recommendation when evidence favors one;
- silently implementing a value-dependent, hard-to-reverse architecture choice;
- treating the current implementation as accidental without checking history;
- asking the user to design an evaluation that evidence can answer;
- accepting popularity without current mechanism evidence;
- collapsing cost, speed, and quality into one arbitrary score;
- replacing a load-bearing guarantee for simplicity;
- accumulating another workflow when the baseline can be extended.
