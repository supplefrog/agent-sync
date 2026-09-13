---
name: context-resilient-orchestration
description: Use for continuous multi-thread task intake across agents.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [orchestration, context, compression, provenance, threads, lifecycle]
    related_skills: [delegation-workflows, cc-dynamic-workflows, session-search]
---

# Context-Resilient Orchestration

## When to Use

Use when one parent continuously absorbs tasks from multiple conversations or agent hosts, infers broader goals, and must keep working across context compression. Use normal task tracking or `delegation-workflows` for bounded single-session work that does not need cross-thread provenance or compression recovery.

This skill owns durable coordination state and thread lifecycle. `delegation-workflows` owns how to partition and verify a bounded subagent batch; `cc-dynamic-workflows` owns persisted DAG execution.

## Contract

Maintain a regenerable view of work without treating conversational summaries as authoritative. New requests enter the work graph without silently displacing active tasks. Every consequential status, decision, and inferred goal remains traceable to original evidence or a live artifact.

## 1. Intake without displacement

For every substantive request:

1. assign or reuse a stable task ID;
2. attach it to a parent goal when supported, otherwise mark the relationship inferred;
3. record source host, thread/session, message/event identity, and timestamp when available;
4. record status, dependencies, priority, next action, unresolved decisions, and verification state;
5. preserve the user's wording for requirements whose meaning could be lost through paraphrase.

A new task changes priority only when urgency, dependency, or user direction warrants it. Do not abandon in-flight work merely because a newer message arrived. Keep one explicit current action and a visible queue.

## 2. Reconcile claims across threads

Treat a thread as an evidence container, not the unit of task state. Extract source-linked task claims and reconcile them across threads before promoting or updating a task. A claim may be:

- directly completed in its originating thread;
- partially completed, with explicit remaining scope;
- laterally completed by another thread, branch, artifact, or live external change;
- superseded or absorbed by a broader goal;
- contradicted by newer evidence;
- still unresolved.

Cluster related claims into broader goals when shared outcome and evidence support the relationship; label inferred goal links. Do not infer task completion from thread closure, archive state, a stale open flag, or a worker summary. Accepted task state belongs to the host task authority; reconciliation proposes evidence-backed transitions.

## 3. Separate source, evidence, and inference

Use this authority order:

1. live external state and artifacts;
2. original raw conversation events;
3. source-linked extracted claims;
4. compression or child summaries;
5. unsupported inference.

Compression summaries and child reports help discovery; they do not prove intent, completion, tests, publication, or current state. Mark inferred goal links and stale-state judgments as inference until corroborated. Preserve contradictions and supersession explicitly instead of rewriting history into one clean narrative.

## 4. Survive compression

Keep the conversational parent small: current priorities, shared constraints, unresolved conflicts, decisions, and stable references. Do not import worker transcripts or broad historical narration.

Before expected compression, or after a major state transition, checkpoint the task graph and evidence handles. After compression:

1. restore the queue from the durable task system or ledger;
2. identify claims based only on a compressed handoff;
3. re-read original events or live artifacts before consequential action;
4. resume from the next verified action rather than repeating completed work.

Use incremental cursors, event IDs, or hashes when scanning append-only stores. Avoid repeatedly summarizing summaries.

Treat worker execution state, result availability, and result delivery as separate facts. A completed child with pending delivery is not still running; recover its final artifact by the retained result handle, verify it, and prevent the lagging delivery marker from creating duplicate work.

## 4a. Gate derived state and ledger changes

A task-board or provenance substrate remains staged until its exact artifact version passes its admission gates. Bind independent review and evidence summaries to artifact hashes; any post-review edit invalidates the review for the changed artifact. If a reviewer finds a material defect, reopen the task immediately and preserve the prior PASS/FAIL history rather than rewriting it.

For cross-provider metadata ledgers:

- keep native provider stores authoritative and task authority separate;
- key identities by provider-native IDs, not titles, cwd, or inferred similarity;
- treat workspace/project paths as observations because one lineage can cross workspaces;
- preserve source gaps and contradictory assertions instead of filling them from summaries;
- validate every direct write API, migration, replay, and crash-recovery path—not only the main importer;
- store bounded structured metadata only; column names alone do not prove payload exclusion;
- verify privacy after transaction/WAL close and reopen;
- keep provider mutation disabled until receipts, reconciliation, idempotency, and readback are separately admitted.

See [references/cross-provider-inventory-and-ledger-gates.md](references/cross-provider-inventory-and-ledger-gates.md) for provider-specific authority rules, source-gap classes, and review gates.

## 5. Route persistence by owner

- Stable user facts and preferences → user memory.
- Stable environment facts → operational memory.
- Reusable workflow, correction, or technique → owning class-level skill.
- Temporary progress, queue state, and dependencies → task ledger, not memory.
- Evidence and deliverables → source artifacts with stable handles.
- Session-specific detail that helps future execution → `references/` under the owning skill.

Do not turn transient failures, process IDs, issue numbers, or short-lived completion state into memory.

## 6. Use threads deliberately

Create a separate temporary thread or worker when the scope has independent success criteria, needs substantial exploration, or would pollute the parent context. Keep coupled and trivial work together. Supply a bounded context packet: goal, source evidence, constraints, ownership, authorization, expected artifact, verification, and failure behavior.

Integrate child output only after verifying its artifact or source evidence. Retain the smallest useful result and handle; do not copy the full transcript into the parent.

## 7. Close stale work safely

Temporary agent-created threads should close when their useful result is integrated and no active task references them. Before deletion or closure:

1. preserve required evidence and artifact handles;
2. verify no active dependency points to the thread;
3. distinguish completed, superseded, blocked, and abandoned work;
4. use the host's supported close/delete primitive and verify the result.

Never delete user-created, shared, active, or referenced threads. If deletion is unavailable, release or close the worker and retain only the distilled result.

## 8. Review the board by decisions

Present work as broader goals with task status, dependency, next action, and the smallest user decision required. Do not dump every thread. Surface contradictions, ambiguous inferred goals, irreversible actions, and blocked dependencies first. Continue autonomously on supported, reversible work.

## Verification

Before reporting orchestration state:

- every active task has a source or explicit inference label;
- every completed task has artifact or execution evidence;
- compressed summaries are not the sole support for consequential claims;
- only one task is marked as the current action;
- temporary workers are closed or intentionally retained with a reason;
- durable lessons are routed to memory or skills, not left only in chat.

See [references/ledger-contract.md](references/ledger-contract.md) for the minimum record shape and compression recovery checklist.

## Pitfalls

- Treating the latest message as an implicit cancellation of all previous work.
- Building a task board from summaries without original-event pointers.
- Declaring completion from a worker's self-report.
- Keeping all exploration in the parent until compression destroys distinctions.
- Saving temporary task state as permanent memory.
- Leaving completed temporary workers open.
- Deleting a thread before preserving evidence or checking references.
- Creating one narrow skill per orchestration incident instead of updating this umbrella.
