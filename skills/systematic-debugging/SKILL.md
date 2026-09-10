---
name: systematic-debugging
description: Investigate reproducible bugs, test/build failures, performance regressions, integration faults, and unexpected system behavior by gathering evidence, isolating the failing boundary, testing causal hypotheses, and validating the real fix. Also use for RCAs after repro, root cause, fix, and validation are known. Skip the full workflow for straightforward supported operations with an obvious direct check.
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [debugging, troubleshooting, root-cause, investigation, rca]
    related_skills: [test-driven-development, code-change-verification, runtime-debugger-tools]
---

# Systematic Debugging

Debugging is causal work: establish what failed, find where the system diverges from expected behavior, test the cheapest discriminating hypothesis, then fix and verify the mechanism.

Do not turn this into ceremony for simple config edits or known supported operations. The amount of investigation should scale with uncertainty and blast radius.

## 1. Establish the failure

Capture the concrete symptom:

- exact error, incorrect output, state, timing, or user-visible behavior;
- reliable or probabilistic reproduction steps;
- expected behavior and evidence for that expectation;
- relevant environment, version, config, and recent changes.

Read complete errors and stack traces. Reproduce with the smallest realistic command when possible. If the failure is intermittent, record frequency and correlated state instead of pretending one non-reproduction disproves it.

## 2. Build a causal split

List plausible causes only when the system has real competing boundaries. For each candidate, identify the cheapest check that would falsify it.

Useful evidence includes:

- logs at the failing timestamp;
- process, port, environment, and config state;
- git diff/history and dependency versions;
- data entering and leaving component boundaries;
- comparable working paths;
- runtime stack/scopes when logs are insufficient.

A useful hypothesis names a mechanism and a disproof condition. “Component X is broken” is not a mechanism.

## 3. Isolate the failing boundary

Trace backward from the symptom or forward from the entry point:

- inputs and validation;
- call sites and branch conditions;
- state mutations, caches, persistence, and reloads;
- subprocess/network/database boundaries;
- retries, timeouts, cleanup, and fallback behavior.

In multi-component systems, inspect the boundaries needed to locate where correct state becomes incorrect. Revisit a boundary when new evidence changes what must be checked; avoid repeating checks without a new question. Avoid adding fixes to several layers at once; that destroys causal information.

### Config/local before upstream

For configurable products, check local state before blaming source:

- active config and profile overrides;
- live process environment and command resolution;
- stale workers, ports, caches, or local patches;
- whether disabling the suspected local integration removes the symptom;
- whether the behavior violates a documented product invariant.

Only upstream a source issue after identifying a product-level mechanism, not merely a local workaround that is inconvenient.

### PATH and toolchain faults

When the wrong binary runs:

1. inspect live `PATH` and command resolution;
2. distinguish current-process environment from persistent User/Machine environment;
3. read wrappers and shims before editing or deleting them;
4. verify version-manager activation as well as installation;
5. prefer correcting path precedence/discovery over deleting vendor binaries;
6. verify in a fresh process.

For the known Windows Node/fnm pattern, load `references/windows-node-path-shadowing.md`.

## 4. Test one hypothesis

Form a hypothesis with a mechanism, supporting evidence, and a disproof condition. Use this structure for reasoning, not a mandatory chat template; explain it when it helps the user understand or steer the experiment.

Run the smallest discriminating experiment. Change one relevant variable at a time. A temporary diagnostic edit is acceptable when read-only evidence cannot isolate the boundary, but remove it after the experiment.

If disproved, update the causal split using the new evidence. Do not stack speculative fixes.

## 5. Contain harm, then fix the mechanism

If ongoing harm makes diagnosis too costly to wait for, use an authorized, reversible mitigation first. Preserve diagnostic evidence when safe, verify that harm is reduced, and record how to undo the mitigation. Label it containment, not proof of root cause or permanent resolution; keep the unresolved diagnosis explicit.

Once the mechanism is supported:

- fix the source of invalid state or behavior rather than only its visible symptom;
- preserve surrounding contracts unless changing them is required;
- add a regression test when it is the cheapest durable proof;
- avoid unrelated cleanup.

Use `test-driven-development` when a failing automated test can capture the bug. Use `code-change-verification` before shipping a nontrivial or high-risk diff.

## 6. Validate at the production seam

Verify:

1. the original reproduction now succeeds;
2. a nearby boundary/regression case still works;
3. state persists/reloads correctly when relevant;
4. fallback/error behavior remains valid;
5. fresh-process or startup behavior for environment/lifecycle fixes;
6. no new targeted test, lint, or type failures.

For large repositories, use targeted and nearby tests locally and CI as the authoritative full matrix unless the full suite is fast and known-clean. Separate unrelated baseline failures from regressions introduced by the fix.

## Failed-attempt escalation

When experiments stop distinguishing causes or producing new evidence, stop speculative patching and revisit the model; do not wait for an arbitrary number of failed fixes:

- Was the reproduction incomplete?
- Is shared state or another component involved?
- Did a local workaround hide the real boundary?
- Does each attempted fix reveal architectural coupling?

Resume with a new discriminating check. If none is available, report the evidence gap and the access, observation, or decision needed; do not loop on equivalent experiments. If the fix requires a broad architectural change or infrastructure mutation, explain the evidence and tradeoff before proceeding.

## Agent-behavior failures

Investigate recurring, consequential, or explicitly requested agent-behavior failures at the owning mechanism. A local correction alone does not establish a need for durable changes. For such investigations:

- reproduce the bad decision or state transition;
- trace input → applicable instruction/skill → model/tool boundary → persisted transition → user-visible output;
- identify why the intended rule was absent, failed to trigger, lost at a boundary, conflicted, or was unenforced;
- change the narrowest owning mechanism, including sibling paths that can create the same failure;
- add a behavioral regression at the production seam;
- verify the original failure is prevented and nearby valid behavior still works.

Do not patch the nearest loaded skill unless it owns the failure class. Do not close the RCA merely because the failed artifact was corrected; if the owning mechanism cannot yet be changed, preserve that as an explicit blocker.

## RCA handoff

Write a postmortem only when these are known:

- **Reproduction/symptom**
- **Root cause mechanism**
- **Fix**
- **Validation scope**

Use concise sections as relevant: summary, symptom, root cause, why it produced the symptom, fix, discovery, why it escaped, validation, and action items. Preserve concrete identifiers and evidence. Separate confirmed facts from hypotheses; do not invent owners or action items.

## Pitfalls

- A plausible explanation is not evidence.
- “Try this and see” is useful only when the result discriminates between hypotheses.
- Reading changed lines without tracing callers/state often finds symptoms, not causes.
- One passing run does not prove an intermittent bug is fixed; compare rates or state when needed.
- Process rigor should reduce uncertainty, not maximize steps.
