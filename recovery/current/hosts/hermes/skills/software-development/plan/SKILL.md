---
name: plan
description: Use when the user explicitly wants an implementation plan instead of execution, invokes plan mode, or needs a durable multi-step handoff before coding. Inspect read-only context, write one actionable markdown plan under .hermes/plans/, and do not implement. Do not trigger merely because a coding task has multiple steps.
version: 3.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [planning, plan-mode, implementation, handoff]
    related_skills: [spike, test-driven-development, code-change-verification]
---

# Plan Mode

Use this when the deliverable is a plan, not working code.

## Boundaries

For this turn:

- Inspect the repository and relevant evidence with read-only tools.
- Do not implement, mutate project files, install packages, commit, push, or perform external side effects.
- The only file you may create or edit is the requested plan document.
- If the user explicitly supplied another output path, use it. Otherwise save under `.hermes/plans/` in the active workspace.

Do not force plan mode onto ordinary implementation requests. The parent can keep a short internal/todo plan while executing without creating a durable plan document.

## Planning workflow

### 1. Establish the target

Capture:

- intended user-visible or system behavior;
- acceptance criteria;
- constraints and non-goals;
- relevant current behavior or architecture;
- unresolved decisions that materially change implementation.

Ask only when missing information changes the plan. Otherwise inspect and state labeled assumptions.

### 2. Inspect enough of the real system

Locate the likely entry points, call paths, state/persistence boundaries, tests, project conventions, and build commands. Prefer exact paths supported by inspection. Do not invent line numbers, APIs, files, or code that have not been checked.

For bug work, identify the reproduction and likely diagnostic phase before prescribing a fix. A plan should not turn an unverified hypothesis into implementation fact.

### 3. Choose the right granularity

Break work into coherent, independently verifiable tasks. A task should produce a meaningful state transition or artifact—not an arbitrary two-minute micro-step.

For each task include, when relevant:

- **Outcome:** what becomes true.
- **Files/components:** exact known paths; label uncertain paths as discovery targets.
- **Changes:** behavior and interfaces to add, remove, or preserve.
- **Verification:** exact test/probe and expected evidence.
- **Dependencies:** what must be completed or learned first.
- **Risk/rollback:** only when the task changes contracts, data, config, deployment, security, or lifecycle behavior.

Include code snippets only when they remove real ambiguity. Do not make plans enormous by duplicating implementation that the coding agent can derive from inspected source.

### 4. Scale discipline to risk

- Use test-first steps when a failing test is the cheapest reliable specification.
- For mechanical/config/environment changes, use the real acceptance probe instead of ritual TDD.
- For parser/router/stateful/persistent changes, include deeper-path or reload verification.
- For migrations or public contracts, include compatibility, rollout, and rollback.
- For broad or uncertain designs, recommend a spike before production implementation when an experiment can cheaply retire the main risk.

### 5. Review the plan

Before saving, check:

- Every stated requirement maps to at least one task and verification step.
- Task order respects dependencies.
- The plan distinguishes confirmed facts from assumptions.
- Scope is complete without speculative features or unrelated cleanup.
- Verification exercises the real production seam where practical.
- The implementer can start without redoing the entire investigation.

## Document shape

Use only sections that add value:

```markdown
# <Title>

## Goal
<target behavior and definition of done>

## Current state
<relevant inspected facts and labeled assumptions>

## Approach
<short causal design and key tradeoff>

## Tasks
### 1. <Outcome>
- Files/components:
- Changes:
- Verification:
- Dependencies/risks:

## Final verification
<integration, regression, rollout, or manual acceptance checks>

## Open decisions
<only unresolved choices that genuinely remain>
```

## Save and report

Default path:

```text
.hermes/plans/YYYY-MM-DD_HHMMSS-<slug>.md
```

Use the active workspace and backend-aware file tools. After writing, read back enough to verify the file and then report the saved path plus the plan’s approach in one or two sentences.

## Pitfalls

- Planning is not implementation theater: do not prescribe code before understanding the path.
- Exactness is valuable only when grounded; fabricated precision is worse than a labeled discovery step.
- Frequent commits, TDD, subagents, and full-suite tests are tools—not mandatory decorations on every task.
- Do not end by forcing an execution workflow. The user can choose how to implement the saved plan.
