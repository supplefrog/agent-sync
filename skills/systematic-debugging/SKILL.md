---
name: systematic-debugging
description: Use for hard bugs, regressions, failing tests/builds, and unexpected behavior that needs causal diagnosis. Skip the full workflow for straightforward fixes.
version: 2.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [debugging, troubleshooting, root-cause, investigation, rca]
---

# Systematic Debugging

Use a short causal loop: establish the failure, locate where behavior diverges, test a check that distinguishes competing causes, then fix the supported mechanism and verify the original symptom and a nearby valid case through the real execution path. Scale the investigation to uncertainty and impact; straightforward fixes need no full workflow.

When no trustworthy reproduction exists, choose a realistic signal: a test, CLI fixture, captured request/trace replay, browser path, known-good comparison, or timing measurement. For manual runs, record steps and state so observations are comparable. Temporary instrumentation can locate the failure; remove it afterward. Keep an automated regression only when its test boundary represents the actual symptom.

## Safeguards

- **Intermittent failures:** compare frequency and correlated state. One passing run neither disproves the failure nor establishes a fix.
- **Competing causes:** identify mechanisms, supporting evidence, and the cheapest check that could disprove each. Change one relevant variable at a time; fixes across several layers obscure causality.
- **Local versus upstream:** distinguish active configuration, overrides, live process environment, stale workers/caches, local patches, and command resolution from documented product behavior. Disabling a suspected integration can isolate its role. Report an upstream defect only when evidence supports a product-level mechanism.
- **Wrong binary:** inspect resolution and wrappers, distinguish tool installation from activation, and prefer correcting path precedence/discovery over deleting vendor binaries. Verify environment and lifecycle fixes in a fresh process. For Windows Node/npm/fnm faults, use [the PATH diagnostic reference](references/windows-node-path-shadowing.md).
- **Containment:** when ongoing harm cannot wait for diagnosis, use an authorized, reversible mitigation. Preserve evidence when safe, verify harm is reduced, and record rollback. Keep unresolved diagnosis explicit; mitigation does not prove root cause or permanent resolution.
- **Verification:** check persistence/reload and fallback/error behavior when the changed mechanism affects them. Separate existing baseline failures from regressions introduced by the fix.
- **Stalled investigation:** when experiments stop distinguishing causes or producing evidence, revisit the reproduction and causal explanation. Resume with a new discriminating check; if none is available, report the missing observation/access/decision instead of repeating equivalent experiments.

## Agent-behavior failures

For recurring, consequential, or explicitly requested agent failures, trace input → applicable instruction/skill → model/tool boundary → persisted transition → user-visible output. Identify absent rules, failed triggering, conflicts, lost context, or unenforced transitions. Repair the owning mechanism, including sibling paths that can cause the same failure; correcting an artifact or the nearest loaded skill does not establish resolution. A local correction alone does not justify durable changes. Use `instruction-authoring` before durable instruction edits; keep an unchangeable owning mechanism explicit as a blocker.

For requested postmortems, use the host's available postmortem workflow with the confirmed symptom, cause, fix, and validation scope.
