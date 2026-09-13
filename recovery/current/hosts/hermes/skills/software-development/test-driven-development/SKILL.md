---
name: test-driven-development
description: Use test-first development when a nontrivial behavior change, reproducible bug, shared contract, or risky refactor is most cheaply specified by a failing automated test. Do not force TDD for exploratory spikes, documentation/config edits, environment repairs, generated files, or mechanical changes whose real acceptance probe is cheaper and clearer.
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [testing, tdd, development, regression]
    related_skills: [systematic-debugging, code-change-verification, plan]
---

# Test-Driven Development

Use TDD when seeing the test fail first materially increases confidence that the requirement is understood and the regression is captured.

TDD is a tool, not a purity test. Choose it because it is the cheapest reliable specification for the change.

## Decision rule

Prefer test-first for:

- reproducible bugs where a regression test can express the symptom;
- behavior changes with concrete acceptance criteria;
- shared logic or public contracts where regressions are costly;
- refactors that need an executable behavior boundary.

Use a direct verification path instead for:

- documentation, formatting, or declarative config;
- local environment/startup fixes whose proof is a fresh process or live state;
- exploratory throwaway spikes;
- generated artifacts;
- mechanical repairs where a targeted command proves the result more directly.

If a test harness is missing or adding one would exceed the risk of the change, do not build testing infrastructure by reflex. State and run the real acceptance probe.

## Red–green–refactor

### 1. RED: express one behavior

Write the smallest test that demonstrates the required behavior through the appropriate production interface.

A useful red test:

- names the observable behavior;
- fails because the behavior is absent or wrong, not because setup is broken;
- avoids asserting irrelevant implementation details;
- uses real code and realistic state where practical.

Run it and inspect the failure. If it passes immediately, determine whether the behavior already exists, the reproduction is wrong, or the test misses the failing path.

For existing bugs, reproduce before changing production code when practical. If exploration was needed to locate the mechanism, keep the exploration separate and still add the regression test before the final fix when it adds durable value.

### 2. GREEN: make the smallest complete fix

Implement enough to satisfy the behavior without unrelated cleanup or speculative flexibility. “Smallest” does not mean patching a symptom while leaving the root cause intact.

Run the red test until it passes. Then run nearby tests that cover the changed contract or subsystem.

### 3. REFACTOR: improve only with green tests

After behavior passes:

- remove duplication introduced by the change;
- improve names or structure where it clarifies the mechanism;
- preserve public contracts unless changing them is part of the requirement.

Keep the relevant tests green. Do not use the refactor step as permission for unrelated redesign.

## Validate the test before trusting green

Treat every new or materially changed test as an untrusted specification proposal.

- Derive assertions from an external requirement, reported reproduction, contract, property, reference behavior, or independently reviewed example—not by copying the current implementation's output.
- A test failing the current implementation may be valid bug evidence. Classify the mismatch before changing the test; do not automatically repair or discard a failing test to make the suite green.
- Require a negative control when practical: show that the test fails on the known buggy/pre-fix behavior or on a small representative mutation. If it cannot distinguish a plausible wrong implementation, strengthen or remove it.
- Scale additional challenge methods to risk and domain support: mutation testing for assertion strength; property, schema, metamorphic, differential, fuzz, or stateful checks for broader behavior; held-out compositional checks for long-horizon agent work.
- When test gaming or author bias is a material risk, protect the evaluator surface and use a fresh author-distinct validator to inspect the frozen requirement, candidate change, and independent challenges. Hidden tests guide final evaluation, not the implementation loop.
- If no independent oracle can resolve ambiguous behavior, report the claim as not proven and escalate the missing product decision instead of manufacturing expected behavior.

These gates validate the test's evidentiary value; they do not require every small change to run mutation testing, spawn another agent, or build hidden-test infrastructure.

## Test the real seam

A regression test should exercise the code path that failed:

- Persistence bug: drive the write, reload, and read path.
- Cache/ledger/merge bug: call the production entry point instead of recreating its algorithm in the test.
- Parser/router/completion bug: test the reported path, one deeper realistic path, and fallback behavior.
- Stateful flow: assert initial state, transition, and resulting state or side effect.
- Deletion/absence behavior: distinguish a complete scan from omission caused by filters, pagination, or limits.

Mocks are appropriate at expensive or unsafe boundaries, but a test that replaces the mechanism under test with a mock proves little. Prefer fakes or narrow boundary mocks while keeping the production transition real.

## Verification scope

Run in this order:

1. the regression test;
2. targeted tests for the changed file/subsystem;
3. nearby tests when shared routing, state, config, security, I/O, or lifecycle behavior changed;
4. the full local suite only when it is fast and known-clean; otherwise let CI own the full matrix.

If baseline tests already fail, compare the same command before and after or otherwise separate new failures from existing ones.

## Reporting

Report:

- what test was added or why TDD was not the right tool;
- the observed red failure when test-first was used;
- the green and nearby verification commands/results;
- important untested scope.

Do not claim TDD if the production code existed before the test. Tests added afterward can still be valuable regression coverage; describe them honestly.

## Pitfalls

- Ritual red/green steps do not compensate for testing the wrong interface.
- One happy-path unit test is not enough for stateful, parser-like, or persistent behavior.
- Deleting working exploratory code merely to reenact test-first order is usually process theater; preserve useful exploration, then verify the final production path honestly.
- Test count is not confidence. Coverage of the actual failure mechanism matters.
