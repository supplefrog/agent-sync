---
name: code-change-verification
description: Review and verify nontrivial local code changes before commit, push, PR handoff, or release; also use when the user asks to review, simplify, or clean up recent changes. Combines scope scrutiny, real production-path tracing, risk-based tests, security/correctness review, and optional simplification. Skip tiny obvious edits when one targeted verification command is sufficient.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [code-review, verification, simplify, pre-commit, security]
    related_skills: [systematic-debugging, test-driven-development, github-code-review]
---

# Code Change Verification

Use this as the quality gate for local changes. It replaces generic “be surgical,” mandatory multi-agent review, and three-agent cleanup rituals with one risk-scaled workflow.

The goal is not the smallest diff at any cost. The goal is the smallest **complete and correct** change, verified through the path that actually runs.

## Choose the mode

- **Verify:** determine whether the change is correct and ready to ship.
- **Simplify:** find worthwhile reuse, clarity, or efficiency improvements without changing intended behavior.
- **Both:** default before committing a nontrivial change.

A review-only request authorizes inspection and verification, not edits. Apply fixes only within an authorized implementation or cleanup scope; otherwise report them, including SAFE suggestions.

Do not load this for greenfield design, architecture selection, broad root-cause investigation, or tiny edits with an obvious direct check.

## Workflow

### 1. Establish the claim

1. Read repository guidance and the relevant diff/status.
2. State the intended behavior in one sentence.
3. Identify the changed files and the production entry point they affect.
4. If the claim or scope is unclear, inspect the request, issue, test, or surrounding code before reviewing.

### 2. Scrutinize scope and layer

Ask whether this change should exist at this size and layer:

- Can existing code or configuration provide the behavior?
- Is any abstraction, configurability, fallback, or cleanup unrelated to the requirement?
- Is a narrow patch hiding a root cause that requires a broader coherent fix?
- Is a broad refactor being justified by a narrow bug?

Prefer the minimum sufficient change, not a locally tiny patch that leaves the real mechanism broken.

### 3. Trace the real path

Trace beyond the changed lines:

- entry point and call sites;
- branches, state mutations, persistence, reloads, and side effects;
- error and fallback paths;
- unchanged code whose assumptions the change relies on.

Separate “the diff appears to do X” from “the running path actually does X.”

### 4. Review correctness and risk

Check what is relevant to the change:

- wrong conditions, boundaries, ordering, retries, concurrency, or partial failure;
- input validation, permissions, path traversal, injection, secrets, unsafe deserialization, and trust boundaries;
- changed public contracts, config keys, persistence formats, or lifecycle behavior;
- swallowed errors, resource leaks, unbounded growth, redundant I/O, or startup/hot-path cost;
- unrelated formatting, comments, generated files, or dependency churn.

Do not force every checklist item onto every diff. Follow the actual risk surface.

### 5. Verify according to change shape

Use the cheapest checks that prove the claim:

- **Flat logic:** requested path plus one boundary or error case.
- **Parser/router/completion tree:** requested path, one deeper realistic path, and fallback behavior.
- **Stateful or persistent flow:** initial state, transition, resulting state/side effect, then persistence reload when relevant.
- **Retryable API write:** verify duplicate prevention against the endpoint's actual semantics through the real producer/helper/client boundary, including ambiguous failure and restart where relevant. For keyed idempotency, durably persist the operation's key before the first attempt and reuse it after ambiguous failure or process restart with the same payload within the provider's deduplication contract. For inherently idempotent operations, verify stable resource identity and repeated-request semantics; do not require an extra key. Without a supported safe-retry mechanism, reconcile remote state before retrying; if the outcome remains ambiguous, stop rather than risk duplicating the write.
- **Environment/profile/startup change:** current process, fresh process, and startup/runtime cost if modules, disk scans, or subprocesses were added.
- **Bug fix:** original reproduction plus one nearby regression check.
- **Deletion/pruning/absence logic:** verify a complete scan and a bounded, paginated, or filtered scan. Omission from a partial result is not proof of deletion.

Regression tests must drive the real production seam. Do not recreate the proposed cache, ledger, merge, or state transition inside the test and then assert that duplicate test logic.

For new or materially changed tests, load `test-driven-development` and apply its test-validity gate. Keep test-authoring rules in that owner rather than duplicating them here.

Run targeted/regression tests first. Add nearby subsystem tests for shared routing, config, persistence, security, I/O, or lifecycle changes. Use CI as the full matrix for large repositories unless the local full suite is fast and known-clean. Compare against baseline when existing failures could be confused with regressions.

### 6. Simplify only where evidence supports it

Review through three lenses without automatically spawning three agents:

- **Reuse:** proven duplication of an existing helper, registry, constant, or pattern.
- **Quality:** redundant state, copy-paste variation, leaky abstractions, parameter sprawl, or code inconsistent with local conventions.
- **Efficiency:** repeated work, unnecessary broad reads, N+1 behavior, missed safe concurrency, hot-path bloat, or resource leaks.

Require evidence such as an existing symbol, real call path, profile, benchmark, or failing test. Skip style-only churn and speculative abstractions.

Classify proposed fixes:

- **SAFE:** clearly behavior-preserving and directly verified; apply routinely only within the authorized edit scope.
- **CAREFUL:** plausible improvement with semantic risk; apply one at a time and rerun targeted checks.
- **RISKY:** public contract, architecture, concurrency, persistence, security, or broad lifecycle change; do not smuggle it into cleanup.

### 7. Use independent review only when it pays

A fresh reviewer is useful when the diff is nontrivial and one of these is true:

- security/auth/provider/config/persistence/lifecycle code changed;
- the implementation involved ambiguous judgment;
- the diff is broad enough that author bias is a material risk;
- the user explicitly asks for independent review.

Give the reviewer the intended behavior, diff, repository path, and verification output. Ask for evidence-backed blocking findings, not generic suggestions. The parent verifies the findings and owns the final judgment.

Do not require independent reviewers for tiny changes, and do not launch automatic fix-agent loops for issues the parent can correct and verify directly.

## Output

For each blocking finding, report:

- **Finding:** specific defect with file/line when available.
- **Impact:** concrete failure or risk.
- **Evidence:** traced path, input, or test exposing it.
- **Smallest complete fix:** correction that addresses the mechanism.

End with one verdict: **ship**, **fix then ship**, **rework**, or **reject**. If clean, state what path was traced, what commands passed, and the important untested scope.

## Pitfalls

- Code inspection alone is not verification when execution is available.
- A mock-only test may prove the mock, not production behavior.
- A smaller diff is not better if it preserves the bug’s real cause.
- A cleanup pass is not permission to redesign unrelated code.
- Tool output and reviewer summaries are evidence to check, not authority.
