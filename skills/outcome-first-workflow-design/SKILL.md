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

Use this before creating or materially changing a workflow, automation, reusable procedure, or persistent agent behavior. It owns intent reconstruction and solution choice; implementation-specific skills own execution. When explicit user constraints and verified evidence settle the mechanism, route execution to its existing owner without repeating solution selection; new evidence of a constraint conflict warrants reconsideration.

## Contract

Optimize the user's outcome, not fidelity to the mechanism they named. Reconstruct the likely goal, challenge weak assumptions, and inspect what already exists. Reversible implementation is still wasted work when the mechanism cannot deliver the outcome. Preserve explicit constraints and safety boundaries. Reuse, simplify, adapt, replace, or make no change as the evidence warrants.

## Procedure

### 1. Reconstruct intent and recover evidence

Recover existing evidence relevant to the decision: supplied material, prior findings, and the affected implementation or callers. Reuse verified findings; mark stale, conflicting, or missing evidence. Separate the desired outcome, explicit constraints, and load-bearing guarantees from incidental implementation choices. Do not turn missing detail into an intake interview. Infer from evidence and resolve consequential unknowns with the cheapest available check. Ask only when a material user-owned preference or hard-to-reverse commitment cannot be settled by evidence.

### 2. Describe the outcome contract

State only decision-relevant outcomes, constraints, failure boundaries, and observable checks. Prefer measurable results over labels such as simple, smart, fast, or robust.

### 3. Check feasibility before implementation

Inspect the relevant baseline and rationale. Identify what is already solved, what is load-bearing, and where the claimed gap appears. Stop when the baseline already meets the outcome.

For an uncertain capability, trace its required inputs and prerequisites. If a known information or performance limit rules out the intended result, reject or revise the approach before coding. Otherwise test the decisive assumption against the baseline using existing evidence, existing tools, or the smallest disposable probe. Before feasibility is established, build only the minimum disposable code or adapter needed to test that assumption. Build further supporting infrastructure only when existing evidence or that probe supports the intended benefit. Permission to code or delegate supplies authority, not evidence of usefulness. Reuse adequate existing evidence; routine fixes with an established cause do not require a new feasibility study.

### 4. Research only decision-changing gaps

Check relevant existing capabilities; reuse an adequate owner. Load additional design or placement guidance only for a concrete unresolved question in the feasibility check or justified implementation. Search externally only for gaps that could change the decision, using sources suited to that gap. Reuse verified research and inspect a proposed outside implementation before adopting it. Compare credible alternatives, including retain/simplify when relevant; do not require a catalog audit or fixed set of source types.

### 5. Decide from first principles

For each candidate, explain the mechanism that could satisfy the outcome. Compare only decision-changing dimensions: verified task success, failure behavior, latency, total expected cost including retries/verification, compatibility, security, maintenance, and rollback. Apply hard constraints before Pareto comparison. Prefer the simpler reversible option when differences are within uncertainty.

### 6. Keep material decisions traceable

Externalize the decision path while work is live so later context loss cannot turn an assumption into an unexplained architecture:

- Record the outcome, material constraints, evidence, live alternatives, recommendation, decisive tradeoff, assumptions, and the condition that would reopen the choice. Reuse the project's existing plan or ADR owner; otherwise keep the compact trace in the handoff instead of inventing a new ledger format.
- When user constraints fix the choice, record them and proceed within authorization if feasibility is supported. If a known limit rules out the outcome, explain the conflict and identify the smallest constraint or approach change needed. Ask only if resolution requires changing a user-owned constraint.
- When evidence supports one option, present that recommendation and proceed within the user's authorized scope; do not convert option comparison into a questionnaire.
- When material taste or priorities remain unresolved after evidence, present reviewable alternatives and a recommendation before committing, even when the choice is reversible. For unresolved hard-to-reverse choices, request focused selection or approval of the smallest unresolved branch—not a general interview.
- Safety and authorization gates apply separately; a supported choice does not bypass them.
- Do not let workers choose an unresolved material architecture implicitly. Fix shared contracts before fan-out, then let independent work run in parallel only where ownership and dependencies do not collide.
- Treat unresolved, blocked, or abandoned branches as first-class outcomes with reasons and impact. Never hide them in a completion summary.

This section owns decision authority and traceability, not execution machinery. Reuse existing task decomposition, scheduling, acceptance-gate, and worker-lifecycle owners; do not copy another workflow's tree, depth ritual, checker, lease, or scheduler.

### 7. Validate before promotion

Stage instruction and capability candidates outside live discovery and shared config; use an isolated test target for executable automation when its side effects require one. Choose the cheapest checks that prove the outcome and relevant failure boundary. For deterministic automation, run the real acceptance probe plus a regression or boundary case as appropriate. For instruction or trigger changes, use `instruction-authoring` for proportional evaluation; add adversarial, non-trigger, or held-out cases only when they address an actual behavioral risk or an uncertain quality claim. Verify consequential claims and delegated work at the parent boundary. Promote only when the relevant checks establish the required correction or supported improvement without a material regression. Record evidence, unresolved checks, rollback, and reevaluation triggers.

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
