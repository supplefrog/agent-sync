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

Use this umbrella for empirical operation and improvement of the live Hermes product. Route to the narrow branch while preserving a shared inspect-before-change and verify-after-change discipline.

## Routing

- Windows Desktop, Electron/dashboard ownership, renderer/session/process state, migration, updates, browser discovery, and WSL boundaries: `references/desktop-operations/SKILL.md`.
- Desktop Project/session-folder ownership, Home/no-project defaults, Files versus Artifacts scope, and already-local deliverable presentation: `references/desktop-project-scope-and-local-files.md`.
- Model/provider route evaluation, auxiliary slots, answer style, concision, personality, and provider-native output controls: `references/behavior-engineering/SKILL.md`.
- Computer-use latency where the pause may be in model deliberation rather than the desktop driver: `references/computer-use-end-to-end-latency.md`.
- Slow or unexpected context compaction, native-versus-local arbitration, effective-threshold math, long-context policy, and recoverability boundaries: `references/context-compaction-diagnostics.md`.
- Fresh canonical Bot Chat behavior that differs from fresh regular sessions, Bot-Chat-only prompt/tool injection, and Bot Chat versus messaging-session/orchestration semantics: `references/bot-mode-behavior-parity.md`.

## Shared workflow

1. Identify the exact live surface, profile, process, session, and owning configuration or source layer.
2. Capture baseline state and a reproducible symptom or representative behavior probe. Before broad reconciliation work, run the owning coordinator's full read-only checks, including runtime versions and required native fixes; narrow tests can pass while recovery obligations are stale.
3. Separate frontend, backend, persisted state, provider transport, model route, and prompt/instruction causes. For repeated continuation interruptions, compare launcher overrides with effective configuration before changing native limits; distinguish per-run iteration exhaustion, goal-turn exhaustion, paused goal state, and command-approval timeout. Verify the implicated boundary offline while preserving finite budgets and genuine consent checks.
4. Prefer supported config and extension paths; use clean worktrees for source fixes. When investigating automatic learning, inspect Curator, background review, and notification controls separately: disabling library maintenance or hiding notices does not stop post-turn review. Preserve this user's preference for automatic learning, including useful inference expenditure; check executable ownership, approval, and rollback protections before recommending restrictions. Distinguish a reproduced safeguard failure from uncertain lesson quality—an eager review prompt alone proves neither harm nor improvement. When expressing task preapproval in `approvals.smart_policy`, preserve ordinary harmless read access and scope the added permission to authorized actions; a workspace restriction intended for mutations can accidentally deny unrelated safe reads. Check the actual blocked command alongside unrelated deletion, traversal, and credential-exposure controls, then execute the authorized operation through normal approval handling. A guardian classification alone does not verify the interruption is resolved. Retire a temporary policy only when directed and only if its exact value still matches, preserving other operator changes.
5. Change one causal variable at a time and preserve rollback. When an update removes a required native fix, compare the old baseline, selected fix, and current upstream source in a disposable worktree; preserve new upstream interfaces and test before installation. Refresh recovery hashes only after verifying the corresponding behavior. Normalize line endings in temporary comparison copies before interpreting merge conflicts; retain exact original bytes for guarded installation and rollback.
6. Verify at the real production seam in a fresh process/session where state is snapshotted. Before a one-use provider trial, exercise the installed consumer's actual argument, result, and prompt-cache lifecycle offline; a fixture that skips native prompt preparation can falsely reject a valid request. Record safe per-invariant comparisons rather than only a generic failure.
7. Close probe-owned agents, database connections, and logging handlers before deleting disposable Windows state; open handles can make passing assertions end in cleanup failure. Verify process exit and cleanup separately, then report actual execution and distinguish local evidence from upstream assumptions.
8. Explain operations in the user's terms: change, check, share across agents, commit, and push. Keep implementation labels out of routine replies unless they explain a decision or failure. Complete the authorized operation through its owning workflow rather than making the user request each intermediate step; simplicity in presentation must not remove governance checks.
9. Treat a correction that exposes an independently verifiable behavior gap as an investigation trigger: inspect source and live behavior, compare them with the authoritative contract, and take the useful authorized action. Do not stop at agreement or apology when verification or an upstream report is available.
10. For files already on the user's local machine, report the owning task/project and one useful root or launcher path; do not turn local presence into a download/attachment workflow unless transfer was requested.

For delegated Kanban workers, treat board state as a separate production seam: after writing and verifying an artifact, use the native `kanban_complete(summary=..., artifacts=[...])` or `kanban_block(reason=...)` operation with the current task/run identity. A textual handoff is not terminal. If the native board operation is not exposed in the child context, report a capability blocker to the parent and do not bypass the child-context guard with a CLI or direct database mutation.

Use `hermes-agent` for ordinary documented setup/config mechanics; this umbrella is for troubleshooting and evidence-driven behavior changes.
