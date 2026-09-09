---
name: advise-project-approach
description: Use for project-architecture decisions and reviews, not isolated repairs. Compare credible current, native, external, and clean-sheet approaches against user outcomes and constraints.
version: 0.6.0
author: Aarav Kashyap; Agent Signal adaptation
license: MIT
compatibility: Requires project evidence and web research when current external facts can change the recommendation.
metadata:
  tags: [architecture, project-strategy, comparables, cost, tradeoffs]
  related_skills: [outcome-first-workflow-design, neuroarxiv]
---

# Advise Project Approach

Help choose, validate, or correct a project architecture by comparing the current project and constraints against credible existing solutions. Recommend one supported path rather than a fashionable stack or an unranked shortlist.

## Owner boundary

- `outcome-first-workflow-design` owns intent reconstruction, material-decision traceability, and approval boundaries.
- When available, `iterative-blind-research` may expand difficult comparable discovery; it is an optional host accelerator, not a dependency. Otherwise use this skill's bounded audit and evidence discipline.
- `neuroarxiv` owns prior-art synthesis only after ordinary skills, implementations, frameworks, and reference architectures leave a genuinely new project-architecture decision.
- Detailed implementation verification stays with the current host and repository's native owner. Hermes may use `code-change-verification`; other hosts use their equivalent project tests, builds, review, and production-path checks.
- Domain owners such as `frontend-ui-engineering` keep their own design decisions.

This skill owns the project-stage evidence, fit comparison, operating-cost analysis, architecture recommendation, and implementation path. Do not copy the routed owners' procedures here.

Advice, inspection, and review are read-only. For a build or change request, carry out the coherent in-scope implementation and local verification, including necessary reversible setup already covered by the request. Preserve the user's existing authorization; ask only for an action that still requires it. Do not infer authorization for publishing, purchases, or unrelated external effects from a request for advice.

## Modes

- **Pre-build strategy:** no implementation exists; choose the first useful architecture and vertical slice.
- **Mid-build correction:** inspect the current implementation and decide what to retain, change, or defer.
- **Post-build review:** assess architecture, operations, security, maintainability, deployment readiness, and gaps.

A repository, folder, code excerpt, or project URL normally means mid-build. “Finished,” “production,” or “launch-ready” normally means post-build. If files are unavailable, proceed from the description and mark file-level conclusions provisional.

## Procedure

1. **Recover the decision context.** Read the request, project guidance, repository evidence, relevant prior decisions, and current architecture. Identify the product goal, users, stage, hard constraints, deployment target, budget/cost sensitivity, team capability, scale, integrations, and failure cost. Use supported reversible defaults; ask only about unresolved user-owned values that materially change the product.
2. **Trace the current baseline.** For an existing project, inspect the relevant docs, manifests, entry points, subsystem boundaries, tests/CI, data/auth paths, and deploy/runtime configuration. Map first and sample decision-relevant slices; do not read an entire large repository by default.
3. **Audit existing solutions.** Check enabled skills and host-native features first. Then inspect credible direct/adjacent projects, official templates, reference architectures, frameworks, standards, and primary documentation. Use two useful comparables when available; record what transfers and what should not be copied. Popularity is a lead, never the decision rule.
4. **Check current cost and constraints.** When a managed service or vendor affects the decision, inspect official pricing, limits, lock-in, migration path, and cost growth. Separate prototype, launch, and growth costs. If current pricing is unavailable, name the unverified cost dimensions instead of inventing numbers.
5. **Compare viable paths.** Compare decision-relevant options, including retain/simplify, native or external replacement, and a minimal rebuild when credible. Compare only decision-changing dimensions: user fit, build speed, reliability, security/privacy, maintenance, operational burden, cost, portability, ecosystem maturity, migration risk, and rollback. Avoid fake precision.
6. **Recommend one path.** State the decisive tradeoff, what the user gains, what they give up, what becomes harder later, and the evidence or condition that would make the recommendation wrong. Name the strongest alternative and why it lost.
7. **Give the implementation path.** Order the smallest useful vertical slice, next integration boundary, and verification/deploy hardening. If implementation is authorized, route execution to the host's available development and verification owners, or use the repository's existing tests/build/review path when no named owner exists. Preserve the recommendation's constraints.

## Evidence discipline

Keep a compact ledger of claim/decision, source, observed date for current facts, support, and limit. Prefer local source, official docs, canonical repositories, standards, releases, tests, and official pricing. Community evidence can expose operational failure modes, but trace material claims upstream when possible.

Do not claim maintenance, adoption, security, performance, price, quota, or production readiness from memory or a search snippet. If external research is blocked, continue from local evidence and label the gap. Stop when the recommendation and strongest alternative are supported and further browsing cannot change the decision.

## Output

Scale the response to the decision, but preserve:

1. **Recommendation** — one path and why it fits.
2. **Evidence status** — project material and external sources actually inspected; gaps clearly labeled.
3. **Constraint fit** — the constraints that drove the choice.
4. **Comparables** — what transfers and what does not.
5. **Alternative and tradeoff** — what it improves and worsens.
6. **Cost/vendor reality** — verified limits or named unknowns when material.
7. **Failure condition** — when the recommendation becomes wrong.
8. **Next actions** — a short ordered implementation path.

For a mid/post-build review, cite the important files and inspected scope. Do not turn a narrow question into a long architecture report merely to fill every heading.
