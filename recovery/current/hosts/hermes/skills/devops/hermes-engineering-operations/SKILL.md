---
name: hermes-engineering-operations
description: Use when troubleshooting or tuning live Hermes behavior.
version: 1.0.3
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, desktop, troubleshooting, evaluation, routing, style]
---

# Hermes Engineering Operations

Use this umbrella for empirical operation and improvement of the live Hermes product. Inspect before changing and verify the affected behavior afterward.

## Routing

- Windows Desktop, Electron/dashboard ownership, renderer/session/process state, migration, updates, browser discovery, and WSL boundaries: `references/desktop-operations/SKILL.md`.
- Desktop Project/session-folder ownership, Home/no-project defaults, Files versus Artifacts scope, and already-local deliverable presentation: `references/desktop-project-scope-and-local-files.md`.
- Fresh coordinator handoffs, bounded live probes, and isolated staged-skill loader checks: `references/live-desktop-probes.md`.
- Model/provider route evaluation, auxiliary slots, answer style, concision, personality, and provider-native output controls: `references/behavior-engineering/SKILL.md`.
- Computer-use latency where the pause may be in model deliberation rather than the desktop driver: `references/computer-use-end-to-end-latency.md`.
- Context compaction, native-versus-local arbitration, effective thresholds and recoverability: `references/context-compaction-diagnostics.md`.
- Approval interruptions or design-only task authorization: `references/approval-boundary-review.md`.
- Fresh canonical Bot Chat behavior that differs from regular sessions and Bot-Chat-only prompt/tool injection: `references/bot-mode-behavior-parity.md`.

## Shared workflow

For repeated systemic complaints, show a compact complaint → responsible mechanism → verified status → next action map. Within explicit reset authorization, reversibly disable the obstructing policy or automatic trigger while preserving safety boundaries, execution capabilities and existing-run contracts. Do not make another broad audit a prerequisite for unblocked delivery.

1. Identify the requested operation, surface, profile, process, session and owning config/source. Reuse its verified native runbook before repairing it or switching to GUI control. `session-librarian` owns Desktop session operations; failure at a different API boundary is not evidence that the requested operation needs repair.
2. Capture a reproducible symptom or representative probe. Reuse completed evidence for design-only continuations; source inspection does not authorize live trials or deployment. Before broad reconciliation, run the owning coordinator's read-only checks, including versions and required native fixes.
3. Separate frontend, backend, persisted state, transport, model route and instruction causes. For continuation interruptions, compare launcher overrides with effective config and distinguish iteration exhaustion, goal-turn exhaustion, paused goals and approval timeout. Preserve finite budgets and consent checks.
4. Prefer supported config/extensions and clean worktrees for source fixes. Inspect Curator, background review and notifications separately: hiding notices or disabling library maintenance does not stop post-turn review. Preserve useful automatic learning while checking executable ownership, approval and rollback boundaries; eagerness alone proves neither harm nor improvement. For approval friction, use the linked approval-boundary procedure rather than inventing broader permission machinery.
5. Change one causal variable at a time and preserve rollback. If an update removed a native fix, compare its old baseline, selected change and current upstream source in a disposable worktree. Preserve new interfaces and verify behavior before installation or refreshing recovery hashes. Normalize line endings only in comparison copies; keep original bytes for guarded installation and rollback.
6. Report disk changes, fresh-process verification and activation in the running Desktop separately. A new thread may reuse an old backend, and a restarted backend may retain old conversation instructions. Keep missing activation checks explicit. Before a one-use provider trial, exercise the installed consumer's argument, result and prompt-cache lifecycle offline; a fixture that skips native preparation can reject a valid request.
7. Close probe-owned agents, database connections and logging handlers before deleting disposable Windows state. Verify process exit and cleanup separately from passing assertions.
8. Complete authorized work through its owning workflow without requiring reminders for routine stages. Lead with the change, check and remaining decision, not internal terminology. A reproduced correction warrants useful investigation, not only an apology; it does not automatically authorize adjacent deployment or durable rules.
9. For already-local files, identify the owning project and useful file or launcher; do not create a transfer workflow unless requested.

Assigned Kanban workers must use the native terminal transition after verifying their artifact. A textual handoff is not board completion; if the operation is unavailable, return the blocker to the parent rather than bypassing the child guard through CLI or database writes.

Use `hermes-agent` for ordinary documented setup/config mechanics; this umbrella is for troubleshooting and evidence-driven changes.
