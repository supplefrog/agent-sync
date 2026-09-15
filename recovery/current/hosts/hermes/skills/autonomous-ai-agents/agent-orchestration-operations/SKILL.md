---
name: agent-orchestration-operations
description: Use when the user calls the agent “the orchestrator,” says “resume the orchestrator,” or coordinates agents, workers, coding CLIs, durable Kanban queues, autonomous dispatch, or cross-thread reconciliation. Prefer event-driven, authority-preserving execution; surface only decisions that genuinely require the user.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [agents, orchestration, delegation, coding-cli, review]
---

# Agent Orchestration Operations

Use this umbrella for multi-agent coordination beyond one direct Hermes response. Choose the branch by execution surface. Ordinary direct execution remains appropriate when delegation adds no capability, isolation or throughput advantage.

## Fresh-chat invocation

- **“Resume the orchestrator.”** Recover the explicitly selected control-plane source and linked evidence before reconstructing work. If the deployment uses the `agent-orchestration` Kanban board, treat it as the current task source, not a permanent substrate requirement. Continue the highest-priority actionable work without creating a duplicate plan.
- **Calling this agent “the orchestrator” and adding work.** Treat this as a role assignment, not a magic command. Reconcile ordinary phrasing against existing ownership and deduplicate intake without demanding a template.
- **“Orchestrator status.”** Read current authoritative state and direct evidence for every material nonterminal lane and recent decision-bearing change. Report done / working / waiting / needs you; queued, assigned or spawned is not working. Check live claim/activity and spawnable assignees, and recover stranded authorized lanes through supported surfaces. Use `references/human-off-control-plane.md` for the stakeholder brief.
- Session todos are a convenience view, not durable authority. Project task-index layout, control-thread allocation and model choices belong in that project's handoff, not this global skill. Ask only for unresolved decisions that change the correct action.

## Routing

- Conversational OS behavior, cross-session recovery, snapshot side questions and completion-to-next-task inspection: `references/conversational-os-control-plane.md`.
- Continuous intake, provenance, compression recovery, reconciliation and worker lifecycle: `references/context-resilient-orchestration/SKILL.md`.
- Hermes Kanban authority, dependency semantics, safe dispatch and live-run verification: `references/kanban-authority-and-dispatch.md`. Event-driven caretaker implementation, deduplication and adversarial checks: `references/kanban-caretaker-lifecycle.md`.
- Terminal-side coding CLIs, isolated worktrees and parent verification: `references/external-coding-agent-clis/SKILL.md`.
- Delegation, async workflows, completion callbacks and reconciliation review: `references/delegation-workflow-review/SKILL.md`.
- Manual OpenAI-only delegation routing with auxiliary assignments reviewed separately: `references/adaptive-model-routing.md`.
- Admission cost and broad automatic skill/plugin discovery: `references/external-discovery-admission.md`.
- Human-off control-plane design, review-versus-decision state, workspace leases and caretaker retirement: `references/human-off-control-plane.md`.
- Research-gated task specification/promotion and production-seam RCA: `references/research-first-intake-gates.md`.
- Trial/comparison/architecture/promotion scope and anti-progress-theater checks: `references/scoped-terminality-and-progress.md`.
- Agent-neutral work packets, cross-surface handoffs, framework boundaries and stakeholder receipts: `references/agent-neutral-context-and-framework-boundary.md`.
- Learning when another implementation merges instead of an authored attempt: `references/merged-fix-learning.md`.
- Session ownership and destructive cleanup: `references/session-lifecycle-cleanup.md`.

## Shared contract

1. Define the bounded outcome, authority, artifacts and acceptance checks. Preserve provenance; reconcile a local implementation against the broader goal and relevant competing work before accepting narrow tests as sufficient.
2. Normalize writable roots before dispatch. Serialize same-root writers unless isolated; establish a baseline commit before choosing a Git worktree, otherwise use a temporary copy or serialization.
3. Keep intake, production, independent review and stakeholder roles explicit. Pass bounded work packets containing the outcome, constraints/approvals, state, dependencies, decisions, evidence, acceptance checks and next action. Recover the selected task source and linked artifacts first; use history to locate missing evidence in ordinary recovery. Exclude history only for explicitly artifact-only continuity tests, and do not claim fresh-context or cross-host recovery without exercising it.
4. The parent owns architecture, authorization, integration and final verification. Preserve child guards while resetting child identity/context at the parent boundary. For broad architecture work, refine intent before freezing dependencies; workers may recursively spawn only with parent-visible handles, bounded depth/fan-out/budget, isolated roots, receipts, failure propagation and cleanup. Otherwise keep graph creation with the controller. If lifecycle support fails, serialize through a proven surface rather than simulating concurrency.
5. Distinguish dispatch, execution, review, completion, delivery and reconciliation. Use native review for review-ready work; reserve blocking for genuine prerequisites or decisions, not routine review or external watching.
6. Before continuing a paused thread, inspect its exact latest message and execution result. Distinguish completion, ordinary waiting, exhausted budget, missing capability and approval refusal/expiry. A controller goal cannot renew approval. After authorized retry, reconcile possible prior delivery, revalidate the exact target and submit once through normal checks. Unknown delivery is not permission to resend. Keep failed attempts and new receipts separate; submission permission does not cover another refused operation.
7. For automatic supervision, trace submission through terminal-event production, caller ownership, delivery consumption, reconciliation and next-task selection. Use the bounded procedure in `references/conversational-os-control-plane.md`. Native-child guarantees do not automatically apply to existing-thread continuation. Prefer supported completion events or bounded scheduled checks over repeated model polling.
8. Independent review needs a separate execution context, not an implementer's self-report or reviewer setup attempt. Distinguish tool availability, admission, actual review and deployed reviewer behavior. Bind verdicts to the reviewed diff; verify material findings and propagate changed requirements to affected workers. Keep candidate execution machinery separate from the running coordinator: a verdict through the old runtime does not qualify the new lifecycle.
9. Verify artifacts, tests, process state and external writes separately. Run deterministic checks before reviewer inference. If a broad suite is already red, run the same command at the exact clean baseline and compare failing identities/mechanisms, not just counts; isolate shared-state contamination. Zero new failures is parity, not a green suite or permission to bypass a clean-suite gate. A comparison remains incomplete until each credible finalist is exercised or excluded by a verified constraint.
10. Close temporary workers after integrating their evidence. For intentional supersession, archive/cancel the durable task before or atomically with process termination so recovery does not respawn obsolete work. Assigned Kanban workers must invoke the authoritative terminal tool after verifying artifacts; prose is not a transition. Return an unavailable board operation as a blocker rather than bypassing it.
11. Keep routine board care autonomous and record decisions with accurate provenance. Agent inference, synthetic fixtures, empty clarification replies and copied text are not user decisions. Reconcile the whole material task set on status requests, not just the current lane. Batch routine receipts; surface meaningful starts, changes, reviews, blockers and completion in short briefs. Distinguish assistant prose from Desktop-rendered receipts before proposing a UI workaround.
12. Schedule by the live critical path: acceptance gates, dependencies, review blockers, root conflicts, spawnable profiles and downstream impact. For an explicit fast-track order, persist/read it back and verify the next lane activates after each terminal step. Do not pause event-gated no-change maintenance unless it causes actual contention.
13. Treat natural additions as intake. Check existing ownership and live capability before creating work; an already-enabled install needs verification or overlap review, not another install task. Preserve behavioral baselines before admitting capabilities that could contaminate them.
14. Use `cross-agent-surface-engineering` for broad persistent-surface changes; do not duplicate its ownership, evaluation or promotion procedure. While substrate authority is open, compare credible complete systems against the same outcomes instead of assuming the incumbent must survive. Give material architecture or irreversible direction one bounded adversarial challenge; stop when objections become resolved decisions or explicit risks/tests.
15. Investigate recurring, consequential or explicitly requested failures at the owning mechanism and verify the failure plus nearby valid behavior. A correction alone does not authorize a permanent RCA framework or global rule. Use research-gated procedures only for a control plane that actually requires them.

## Session cleanup boundaries

The runtime/spawner owns lifecycle tracking, not individual skill recipes. A PID, title, source tag, parent link or output path alone grants no deletion authority. Delete only under scoped authorization after useful results are integrated and current ownership, terminal state, inactivity and absence of user adoption/sharing/pins/references are verified. Unknown state means retain. User adoption makes a session durable.

Before destructive approval, explain each candidate's purpose, outcome and supersession, not merely its ID or terminal flag. Preserve the user's selected parent/child boundary. Process reaping is not persisted-session cleanup; consult the lifecycle reference for the typed ownership contract.

## Keep context and repairs proportional

- Continue the same unfinished task in its existing context. Give a distinct substantial task a bounded context when separation helps. When explicitly assigned a coordinator-only role, blocked worker admission does not transfer implementation ownership; otherwise authorized direct execution remains available when coordination is the obstacle.
- Demonstrate task separation, runtime ownership and automatic progression independently; none proves the others or reduced approval interruptions. Apply a user's ownership correction in the next action rather than promising a future feature.
- If an authorized reversible workaround restores the priority workflow, verify it, label the remaining defect and return to that workflow. Do not expand incidental cleanup into a framework or review campaign.
- If redirected during a repair, remove only your abandoned uncommitted changes and verify unrelated work survives. Containment is not a root-cause fix; backend readback is not visible UI recovery.
