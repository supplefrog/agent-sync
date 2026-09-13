---
name: software-verification-workflows
description: Use for software review and verification.
version: 1.0.0
metadata:
  hermes:
    tags: [verification, review, lifecycle, contracts, merge, integrations, kanban]
---

# Software Verification Workflows

Use this class-level umbrella when the task is to judge whether a software change or handoff is correct, safe, complete, and ready to advance. Select the risk-specific branch rather than applying a generic checklist to every change.

## Routing

- Event hooks, plugins, webhooks, retries, idempotency, provenance, and host-runtime boundaries: `references/event-driven-integration-review/SKILL.md`.
- Durable state, ownership, retention, cleanup, recovery, migrations, leases, and destructive APIs: `references/persistence-lifecycle-review/SKILL.md`.
- Three-way merges, cherry-picks, divergent branches, checkout-supersession comparisons, and semantic conflict resolution: `references/semantic-merge-verification/SKILL.md`.
- Structured parser/model/API output, schemas, graphs, durable gates, and fail-closed behavior: `references/structured-contract-verification/SKILL.md`.
- Independent Kanban review-lane handoffs and terminal verdict routing: `references/sdlc-review/SKILL.md`.

## Shared workflow

1. Reconstruct the requested behavior, acceptance criteria, current code/deliverable, and authoritative production seam.
2. Map each material claim to observable evidence and identify the highest-risk state transition or trust boundary.
3. Inspect callers, sibling paths, negative paths, persistence/reload, retries, cleanup, and concurrency only where relevant.
4. Prefer a small deterministic reproducer or production-seam probe over helper-only fixtures or comments.
5. Falsify proposed findings before blocking: search for guards, run the control case, and distinguish baseline failures from change-caused defects.
6. Verify in increasing scope: syntax/import, direct regression, neighboring behavior, then broader quality gates when justified.
7. Report exact file/line or artifact location, concrete impact, reproduction/evidence, smallest complete fix, and a strict verdict.

## Reviewer boundaries

- Review the deliverable rather than the implementer's narrative.
- Do not manufacture findings to fill categories.
- Preserve role separation in independent review lanes; request changes instead of silently implementing them.
- A marker-free merge, green mock, or passing happy path is not sufficient evidence of semantic correctness.
- When cleanup depends on an old checkout being superseded, compare its changes with the installed version and maintained development branch before deletion. Report recoverability, equivalent code, deployed behavior, and comparative quality separately; a backup or reachable commit proves preservation, not that the old implementation is inferior.

Detailed probe recipes and checklists remain inside the routed branch packages.