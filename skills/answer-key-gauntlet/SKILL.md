---
name: answer-key-gauntlet
description: Use when a build exceeds one context or lacks a quality bar.
version: 1.1.0
author: Local User
license: MIT
compatibility: Requires durable project files; subagents are optional.
metadata:
  tags: [planning, specification, delegation, verification, gauntlet]
  canonical_owner: Agent Sync
  related_skills: [outcome-first-workflow-design, dynamic-workflows, code-change-verification]
---

# Answer-Key Gauntlet

## When to Use

Use for a substantial system or feature that will not fit safely in one context window, or where “make it good” has no trustworthy external product to compare against. A simplified Wayfinder produces `.wayfinder/map.md` and `.wayfinder/answer-key.md`; implementation and fresh critics then work against those artifacts.

Do not use for small, already-specified work. Do not treat agent count, magic keywords, or blind model preference as a quality mechanism.

## Long-context continuity

The two `.wayfinder` files are the durable source of truth across context compression, fresh sessions, and delegated workers. Keep conversational context disposable.

- Externalize settled decisions and checks before the active context becomes crowded; do not rely on a summary to preserve them.
- Resume by reading the map, answer key, current repository state, and live task frontier. Do not reconstruct the effort from chat memory.
- Work one coherent phase or task frontier at a time. Start fresh contexts for independent builders and critics rather than carrying their exploration into the parent.
- Compact or hand off at a phase boundary, not during an unresolved decision round or shared-contract change.
- After resuming, verify repository state and recorded evidence before trusting statuses written in an earlier context.
- Update the map when a real decision changes. Never silently let implementation drift become the new specification.

## Protected invariants

- Freeze the answer key before implementation. Builders and critics may not weaken, delete, or reinterpret checks to pass.
- Facts are the agent's job to inspect or research. Ask the user only for product decisions, preferences, and authority boundaries.
- Every material requirement maps to an observable check; every check maps back to a recorded decision or constraint.
- Critics judge only. They do not implement fixes. The integrating agent independently verifies consequential claims.
- Parallelize only independent ownership. Keep foundations, shared contracts, migrations, and integration serialized.
- No “close enough.” A failed or unverified check remains failed or blocked, with evidence.

## Phase 1: Clear the planning fog

1. **Inspect first.** Read the current project, constraints, prior decisions, tests, and primary sources. Use the host's outcome-first workflow skill when available for material workflow or architecture choices.
2. **Name the destination.** State the user-visible outcome, definition of done, scope, non-goals, cost/latency/privacy bounds, and rollback needs.
3. **Build a decision tree.** Identify unresolved branches covering users, jobs, behavior, data, integrations, failure modes, operations, design, and acceptance.
4. **Work the frontier in rounds.** Ask together only questions whose prerequisites are settled. Give a recommended default for each. Recompute the frontier after every answer. There is no target question count.
5. **Research instead of asking for facts.** Resolve repository, API, framework, and environment facts with available tools. Only dependent questions wait.
6. **Stop when the frontier is empty.** Do not silently fill material branches. Record deliberate deferrals as out of scope or blockers.

Then write exactly:

- `.wayfinder/map.md`: destination, scope/non-goals, evidence, decisions with rationale, constraints, failure modes, dependencies, design direction, and blockers.
- `.wayfinder/answer-key.md`: immutable acceptance checks with binary status and reproducible evidence requirements.

Use [references/artifact-contract.md](references/artifact-contract.md). Preserve existing project-owned artifacts unless the user authorizes replacement.

## Phase 2: Validate the key before building

- Trace every destination requirement and map decision to one or more check IDs.
- Reject subjective checks such as “looks polished” unless they include a concrete rubric, reference set, viewport/state, and decision rule.
- Prefer production-seam probes, tests, screenshots, accessibility checks, persistence/reload checks, and negative cases over agent opinion.
- Record the verification command or manual procedure and expected evidence before implementation starts.
- Ask for confirmation only when unresolved product values remain; otherwise proceed on documented reversible defaults.

## Phase 3: Build the task graph

1. Use the host's delegation or task-agent workflow when available.
2. Derive work packages from map decisions and answer-key coverage, not arbitrary layers.
3. Validate required tools before fan-out.
4. Establish foundations and shared contracts serially.
5. Delegate only disjoint slices up to the host's safe concurrency limit. Each worker receives the map, immutable answer key, owned files/scope, relevant check IDs, and required evidence.
6. Integrate at the parent boundary and run direct checks before opening another frontier.

Use the host's task tracker when available. Dependencies, not agent enthusiasm, determine the ready frontier. Without subagents, run the same graph serially and create fresh review context at integration boundaries.

## Phase 4: Builder/critic loop

For each integrated slice:

1. **Builder:** implement the owned slice and return changed paths plus raw check output.
2. **Fresh critic:** in a separate context, inspect the deliverable against assigned answer-key IDs and return `PASS`, `FAIL`, or `BLOCKED` per ID with evidence. The critic must not edit.
3. **Integrator:** reproduce material failures and verify passes at the real seam where practical.
4. **Revision:** send evidence-backed failures to the builder or a bounded fix worker.

Cap a check at three builder/critic cycles. If findings are not shrinking, stop and report the root blocker rather than looping until approval.

## Phase 5: Final gauntlet

- Run every answer-key check from the integrating context, including applicable integration, negative, persistence/reload, visual/accessibility, and regression checks.
- Update only status and evidence fields; never change the requirement or pass rule after the build.
- Finalize only when all required checks pass. Report optional failures separately and blocked required checks as incomplete.
- Keep the map and completed answer key as the handoff. Remove disposable branches, worktrees, and evaluation artifacts after verified integration.

## Output

Report the destination verdict; totals by `PASS`, `FAIL`, and `BLOCKED`; direct commands or artifacts proving the result; unresolved risk and rollback; and links to both `.wayfinder` files.
