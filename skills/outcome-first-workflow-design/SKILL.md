---
name: outcome-first-workflow-design
description: Use for agent workflow design or structural workflow repair, including recurring failures despite checks, and for material changes to automation, reusable procedures or persistent capabilities. Recover the human outcome and baseline, research mechanism alternatives and compare retain/adapt/replace options before building.
license: MIT
compatibility: Requires access to the current artifact and, when external options matter, source or web research.
metadata:
  author: supplefrog
  version: "0.1.2"
---

# Outcome-First Workflow Design

Use this before creating or materially changing a workflow, automation, reusable procedure, or persistent agent behavior. It owns intent reconstruction and solution choice; implementation-specific skills own execution. When explicit user constraints and verified evidence settle the mechanism, route execution to its existing owner without repeating solution selection; new evidence of a constraint conflict warrants reconsideration.

## Contract

Optimize the user's outcome, not fidelity to the mechanism they named. Separate explicit constraints and load-bearing guarantees from incidental implementation choices. Reuse, simplify, adapt, replace, or make no change as the evidence warrants. Scope, authorization and dispatch follow Agent Sync's `surfaces/core.md`; resolve it from the shared fleet's `source_snapshot` and load it before dispatch.

## Procedure

### 1. Reconstruct intent and recover evidence

For an audit of an accumulated agent system, reconstruct behavior clusters from existing instructions, original user decisions and observed outcomes. Present concrete desired/undesired outcomes, mismatches and unresolved user-owned choices; do not ask the user to enumerate the system's requirements from scratch or substitute an inventory for a behavior audit. Keep inferred contracts staged for human clarification. Skills and instructions are candidate implementations; retain, improve or remove them according to their contribution to the required output, with the user as final behavior authority.

Recover supplied material, prior findings, and the affected implementation or callers. Reuse verified findings; mark stale, conflicting, or missing evidence. For material redesign, name the assumptions shaping the approach, inspect whether they prevent the outcome, and compare the strongest credible alternative. Revise assumptions when evidence supports it, without recurring reflection or review. Resolve consequential unknowns with the cheapest available check; do not turn missing detail into an intake interview. Ask only when a material user-owned preference or hard-to-reverse commitment cannot be settled by evidence.

### 2. Describe the outcome contract

State only decision-relevant outcomes, constraints, failure boundaries, and observable checks. Prefer measurable results over labels such as simple, smart, fast, or robust.

### 3. Check feasibility before implementation

Inspect the relevant baseline and rationale. Identify what is already solved, what is load-bearing, and where the claimed gap appears. Stop when the baseline already meets the outcome.

For an uncertain capability, trace its required inputs and prerequisites. If a known information or performance limit rules out the intended result, reject or revise the approach before coding. Otherwise test the decisive assumption against the baseline using existing evidence, existing tools, or the smallest disposable probe. Before feasibility is established, build only the minimum disposable code or adapter needed to test that assumption. Build further supporting infrastructure only when existing evidence or that probe supports the intended benefit. Permission to code or delegate supplies authority, not evidence of usefulness. Reuse adequate existing evidence; routine fixes with an established cause do not require a new feasibility study.

### 4. Research the mechanism before structural repair

For a new or materially redesigned workflow, or recurring failures despite checks, investigate the structural cause and compare credible mechanisms before selecting a repair. Judge alternatives against the human outcome and observed baseline. A mechanism suggested by the user is a candidate unless the user fixes it as a constraint.

Reuse current, source-bound research when it answers the decision; otherwise load `project-prior-art` for proportional search and source inspection. Record which evidence settles the choice and which uncertainty needs a probe. Routine fixes with an established cause and adequate evidence can proceed through their existing owner. Load other design or placement guidance only for a concrete unresolved question in feasibility or justified implementation.

### 5. Decide from first principles

For each candidate, explain the mechanism that could satisfy the whole authorized outcome. Compare only decision-changing dimensions: verified task success, failure behavior, latency, total system complexity and expected cost including retries/verification, compatibility, security, maintenance, and rollback. Patch size is not a proxy for simplicity; do not collapse cost, speed and quality into an arbitrary score. Apply hard constraints before Pareto comparison. Prefer the simpler reversible option when differences are within uncertainty. A focused repair remains appropriate when it meets the requested outcome; an architectural request may require replacing the mechanism. Verify the affected outcome and stop when its criteria are met.

### 6. Keep material decisions traceable

Record the outcome, constraints, evidence, live alternatives, recommendation, decisive tradeoff, assumptions, and condition that would reopen the choice in the existing plan or ADR; otherwise use the handoff. For cross-session continuity, handoff or closeout, load `breadcrumb-records` for record organization and safe continuation.

- When user constraints fix the choice, proceed within authorization if feasibility is supported. If a known limit rules out the outcome, explain the conflict and identify the smallest constraint or approach change needed. Ask only if resolution requires changing a user-owned constraint.
- When evidence supports one option, present that recommendation and proceed within authorized scope; do not convert comparison into a questionnaire.
- When material taste or priorities remain unresolved after evidence, present reviewable alternatives and a recommendation before committing, even when reversible. For unresolved hard-to-reverse choices, request focused selection or approval of the smallest unresolved branch.
- Do not let workers choose an unresolved material architecture implicitly. Settle shared contracts before fan-out, then parallelize only where ownership and dependencies do not collide. Use existing execution owners for decomposition, scheduling, acceptance and worker lifecycle.
- Record unresolved, blocked or abandoned branches with reasons and impact; never hide them in completion.

### 7. Validate before promotion

Choose the cheapest checks that prove the outcome and relevant failure boundary. For deterministic automation, use an isolated test target when side effects require it and run the real acceptance probe plus a regression or boundary case as appropriate. Verify consequential claims and delegated work at the parent boundary.

For acceptance or evaluation workflows, demonstrate that the checks reject relevant faulty outputs and accept nearby valid outputs before using their verdict for promotion. Bind the evidence to the actual artifact or action being judged; metadata, authored pass labels and check counts do not establish the human outcome.

Before authoring instruction or trigger candidates, load `instruction-authoring` for staging outside live discovery, proportional evaluation and regression boundaries. For shared capability admission or promotion, load `cross-agent-surface-engineering` for checked deployment, evidence, rollback and unresolved checks; no candidate is promoted without the required correction or supported improvement and no material regression.

## Output

Return the decision, intended outcome, decisive evidence, chosen mechanism, validation, and remaining uncertainty. Exclude research narration and implementation work that cannot change the decision.
