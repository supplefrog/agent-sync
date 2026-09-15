---
name: software-verification-workflows
description: Use for software review and verification.
version: 1.0.0
metadata:
  hermes:
    tags: [verification, review, lifecycle, contracts, merge, integrations, kanban]
---

# Software Verification Workflows

Judge whether a software change or handoff is correct, safe, complete, and ready to advance. Select the relevant risk branch rather than applying every specialist checklist.

## Routing

- Event hooks, plugins, webhooks, retries, idempotency, provenance, and host-runtime boundaries: `references/event-driven-integration-review/SKILL.md`.
- Durable state, ownership, retention, cleanup, recovery, migrations, leases, and destructive APIs: `references/persistence-lifecycle-review/SKILL.md`.
- Three-way merges, cherry-picks, divergent branches, checkout-supersession comparisons, and semantic conflicts: `references/semantic-merge-verification/SKILL.md`.
- Structured parser/model/API output, schemas, graphs, durable gates, and fail-closed behavior: `references/structured-contract-verification/SKILL.md`.
- Independent Kanban review-lane handoffs and terminal verdict routing: `references/sdlc-review/SKILL.md`.
- Bounded model/delegation trials: load `agent-capability-engineering` and its `references/evaluator-process-evidence-lifecycle.md`; ordinary verification does not require a trial protocol.
- Hermes staged-skill loading: load `hermes-engineering-operations` and its `references/live-desktop-probes.md`.

## Shared workflow

For code, use [code-change-verification](../code-change-verification/SKILL.md) for scope, production-path tracing, regressions and the output contract. For non-code deliverables, map requirements to observable evidence and use that output contract.

1. Reconstruct the requested outcome and acceptance criteria. For a comprehensive system audit, consider keeping, simplifying, replacing or removing mechanisms before proposing item fixes. Trace a failing policy's actual trigger or consumer; another policy layer does not repair invocation.
2. Map each material claim to evidence and the highest-risk transition or trust boundary. Separate mandatory requirements from advisory process preferences. Require an exact skill invocation only when invocation itself is justified by the acceptance contract. Keep task correctness distinct from process compliance without rescoring an original failure.
3. Reuse current identity-bound evidence. Before a costly check, name the failure it detects, the decision it changes and its stopping condition. Run missing or invalidated checks, using the canonical runner and known-good/known-bad controls where relevant. Test counts alone do not establish useful coverage.
4. Trace deferred operations through identity, ownership and approval checks at admission and execution. Inspect native crash recovery as well as wrapper retries. Model-facing provenance notes are not enforceable authorization.
5. Verify execution rather than quoted results: bind commands, exit codes, artifacts and reviewed revisions. A command printing old logs is not a fresh test run. For verifier/harness changes, derive independent expectations and external observations; shared verdict logic only establishes consistency.
6. Reconcile findings and advance the next authorized dependency-ready step. Keep worker completion, parent acceptance and permission to deploy separate. Preserve failures and uncertain outcomes; renewed approval resumes the blocked step, not already-completed work.

## Reviewer boundaries

- Form an initial assessment from requirements and the deliverable before reading the implementer's defense or other verdicts. Then reconcile history so repaired defects are not reopened blindly.
- Use independent review when requested or justified by risk or author bias. Parallelize genuinely independent scopes; primary research is useful when a material design claim needs it, not a prerequisite for every review.
- Fresh conversations do not prove independent errors, scoring or permissions. Disclose shared assumptions and use the smallest separate observation boundary needed for the claim; do not ask reviewers to ignore governing instructions.
- Preserve role separation in independent review lanes: request changes rather than silently implementing them. Check reviewer findings against the real artifact before accepting them.
- A clean merge, green mock or passing happy path is not proof of semantic correctness.
- Before deleting a superseded checkout, compare its unique changes with the installed and maintained versions. Recoverability, code equivalence, deployed behavior and comparative quality are separate claims.

Detailed native lifecycle commands and specialist probe recipes remain with their routed owners.
