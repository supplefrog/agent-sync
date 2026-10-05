---
name: breadcrumb-records
description: Use when work grows into a project, or at handoff, interruption and closeout. Organize owned files and preserve decision reasons, evidence and safe continuation.
version: 1.1.0
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

## Continue, hand off and close out

Keep one discoverable continuation record linked from the existing README, AGENTS.md, task index or equivalent. Write enough for another agent to continue: goal/scope and authorization limits, canonical root/branch/revision, current state and timestamp, decisions with reasons, actual checks and limits, owned artifacts, blockers, next safe action and rollback/recovery path. Preserve exact identifiers when they matter. Link evidence instead of copying chat transcripts. Do not duplicate a README, ADR or existing status record.

Before interruption or delegation, save the current state and next action; do not mark unfinished work complete or clean its active artifacts. On resume, verify current files and ownership before reusing historical status. Concurrent agents use distinct task scratch/ownership records; one writer owns each continuation record.

At completion, verify the deliverables, commands and links; update the record with the result and limitations. Keep architecture rationale beside the decision, with an ADR only for a consequential choice that a later maintainer may revisit. Write concise outcome-first prose; preserve scope, tradeoffs and evidence rather than narration or generic process advice.

Check for a supported reusable method/correction and route it to its existing `instruction-authoring` owner under the current authorization; project facts/taste stay local and memory obeys the host's authorization. A task finishing does not require a new skill. Shared admission and publication retain their own checks.

Inventory task-owned stale scratch, abandoned generated outputs and duplicates only after preserving the authoritative deliverable, context and referenced evidence. Recheck references and other active users. Archive recoverably with exact paths/hashes and a restore route; leave uncertain ownership or changed files pending. Do not sweep by age, name or extension, remove sessions, or delete another task's files. Irreversible purge requires action-time approval. The optional [task artifact helper](scripts/task_artifacts.py) implements explicit file registration, preview, recoverable archive and restore; read [usage and limits](references/task-artifacts.md) before use. It does not infer ownership, find references, promote projects or operate native threads.

## Capture and reuse

1. Keep one compact record per logical change in the project's existing work/docs area. Link it from the existing project index or handoff; do not create a global log. Keep private records outside the shared skill repository.
2. Record the requested outcome and original intent/approval locator when available. Separate observations, hypotheses and decisions. Preserve the chosen approach, material alternatives and rejection reasons in `change.text`; name what evidence would reopen the decision in `checks.limits`. Do not fabricate missing provenance or treat a previous model's conclusion as independent evidence.
3. Link exact diffs/artifacts, actual check output and limitations. Name one authoritative deployment/status receipt, its observation time or explicit unknown time, and session/reload implications. Clearly distinguish historical receipt state from current live state; supersede only the named outdated statement, not the entire source.
4. State the next safe action and rollback path or missing prerequisites. A record does not grant permission to deploy, publish, delete or undo work. If evidence is incomplete, stop the consequential action and identify only the missing lookup/check; do not restart a broad audit.
5. Validate the record and report material gaps. On reuse, inspect the linked evidence needed for the decision; recheck current state only where staleness changes that decision.

## Optional deterministic helper

If an equivalent record already exists, use it directly. Otherwise use [the CLI](scripts/breadcrumb.py) and [format/usage](references/usage.md). Resolve the script from this loaded skill directory, not the project working directory. Use the host's available Python 3.11+ interpreter (`python` or `python3`).

```text
python <skill-dir>/scripts/breadcrumb.py init <project>/change.json
python <skill-dir>/scripts/breadcrumb.py update <project>/change.json --from <temporary-input.json>
python <skill-dir>/scripts/breadcrumb.py check <project>/change.json
python <skill-dir>/scripts/breadcrumb.py render <project>/change.json
```

Complete a copy of the scaffold as INPUT; keep its ID and resolve evidence paths relative to RECORD. Later updates also use a copy, preserving prior revisions. One designated writer owns updates; other agents contribute evidence to it. The JSON is authoritative; Markdown is a generated view. For research or non-deployment work, explicitly state that deployment/rollback is not applicable and use `planned`/`in_progress` for unfinished work; do not label it deployed. This first schema has no generic completed-research status.

The helper checks shape and local file existence, not evidence truth, freshness, authorization or hashes. It does not fetch URLs: use an already-authorized local source extract plus its original URL in the prose, or an existing research record. It has no watcher, automatic capture, networking or agent hooks. Direct edits bypass history preservation. Do not store credentials, raw private transcripts or hidden prompts.

When changing the helper, run [its CLI regression suite](scripts/test_breadcrumb.py): `python -m unittest discover -s <skill-dir>/scripts -p test_breadcrumb.py`. Preserve draft completion, rejected-update nonmutation, scoped history, clean malformed-input errors and broken historical-link warnings. [Provenance and deployment boundary](references/provenance.md).
