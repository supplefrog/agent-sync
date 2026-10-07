---
name: breadcrumb-records
description: Use when work grows into a project, or at handoff, interruption and closeout. Organize owned files and preserve decision reasons, evidence and safe continuation.
version: 1.1.1
license: UNLICENSED
compatibility: Python 3.11+; local evidence files; one writer per record.
---

# Breadcrumb Records

Use when exploratory work becomes durable, or for an explicit breadcrumb, substantial handoff, interruption or closeout. On resume, consult the existing record before repeating the investigation. Keep trivial replies and isolated corrections lightweight; extend an equivalent project record rather than create a duplicate. This skill owns the project lifecycle; architecture choices remain with `project-prior-art`, reusable instruction corrections with `instruction-authoring`, and native thread association with the host adapter.

## Decide and organize

- A casual idea, one answer, or a bounded edit in an existing project => work in place; no new project or template bundle. Reassess when the scope grows, before durable outputs scatter.
- Work needs cross-session continuity, several related outputs, reusable files/sources, another maintainer, or consequential operational context => reuse its existing project; otherwise establish one named root under the user's configured projects root. Time, token count, file count and an enthusiastic idea alone are poor promotion tests. A meaningful risk can justify a small project with one output.
- Confirm the workstream and ownership from registered projects, source and user intent. A dated chat folder or current shell directory alone is not project ownership. Inspect existing conventions, Git status and concurrent work; use a separate worktree for concurrent Git writers. Do not create a duplicate project or put another workstream into this repository.
- When promotion is within the user's authorized work, briefly state the chosen root and continue reversible organization. Thinking aloud alone does not authorize building, publication or broader cleanup. Ask only for a material unresolved destination/ownership choice or a required action-time permission.
- Follow the existing ecosystem layout. For a new root, keep purpose/use in a short README and agent-specific commands/boundaries in AGENTS.md only when useful. Put source, tests, docs, data and deliverables in conventional locations that have real jobs; create no empty scaffolding. Keep secrets and application-managed state at their owners. Use one task-local scratch folder.
- Move only clearly task-owned files through an explicit source/destination inventory, retaining recovery and checking collisions, references, Git/worktree links and entrypoints. Leave uncertain, shared or unfinished files in place. Filesystem organization and native thread/project membership are separate actions: use the supported host adapter, read back the exact project/thread IDs and report any incomplete association. Never edit conversation databases as an automatic fallback. Host procedures and current limits: [project lifecycle adapters](references/host-association.md).

## Record, continue and close out

Keep one compact record per logical change in the project's existing work/docs area, linked from its README, AGENTS.md, task index or equivalent. Extend an equivalent record; do not duplicate a README, ADR or status record, create a global log, or put private records in the shared skill repository.

The record owns these continuation facts:

- Goal, scope, authorization limits and original intent/approval locator or explicit missing provenance; canonical root/branch/revision, current state and timestamp, exact identifiers, owned artifacts and blockers.
- Observations, hypotheses and decisions kept distinct; chosen approach, material alternatives, rejection reasons and evidence that would reopen the decision. Do not fabricate missing provenance or treat a previous model's conclusion as independent evidence.
- Links to exact diffs/artifacts and actual checks with limits, instead of chat transcripts. Name one authoritative deployment/status receipt, its observation time or explicit unknown time, and session/reload implications. Distinguish historical receipt state from current live state; supersede only the named outdated statement.
- Next safe action, rollback/recovery path or missing prerequisites. A record grants no permission to deploy, publish, delete or undo work. Incomplete evidence => stop the consequential action and identify only the missing lookup/check, without restarting a broad audit.

Before interruption or delegation, save state and next action; do not mark unfinished work complete or clean its active artifacts. Concurrent agents use distinct task scratch/ownership records with one writer per continuation record. On resume or reuse, verify current files and ownership, inspect the linked evidence needed for the decision, and recheck live state only where staleness changes that decision.

At completion, verify deliverables, commands, links and record completeness; report material gaps and update the result/limits. Keep consequential architecture rationale beside the decision, using an ADR when a later maintainer may revisit it. Use concise outcome-first prose.

Route supported reusable methods/corrections to the existing `instruction-authoring` owner under current authorization; project facts/taste stay local and memory obeys host authorization. Completion alone requires no new skill and grants no shared admission or publication authority.

## Recover owned artifacts

After preserving the authoritative deliverable, context and referenced evidence, inventory task-owned stale scratch, abandoned generated outputs and duplicates; recheck references and active users. Archive recoverably with exact paths/hashes and a restore route. Leave uncertain ownership or changed files pending; do not sweep by age, name or extension, remove sessions, or delete another task's files. Irreversible purge requires action-time approval.

For optional explicit registration, preview, archive or restore, read [task artifact usage and limits](references/task-artifacts.md) before invoking its helper. That reference owns exclusive ownership, hash checks, refusal conditions, concurrency limits and recovery procedures; the helper cannot infer ownership/references, promote projects or operate native threads.

## Optional record helper

Use an equivalent existing record directly. When choosing the optional JSON CLI, read [record format, commands and limits](references/usage.md) before invocation; that reference owns the helper procedure. When interpreting the skill's prior validation or deployment evidence, read [provenance and scope](references/provenance.md).
