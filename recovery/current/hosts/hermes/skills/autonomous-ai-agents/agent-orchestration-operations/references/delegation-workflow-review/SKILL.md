---
name: delegation-workflow-review
description: Review changes to delegation, async workflow, or orchestration code with attention to preserved capabilities, background callbacks, and reconciliation paths.
version: 1.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [github, code-review, delegation, workflows, async, orchestration]
---

# Delegation Workflow Review

Use this skill when reviewing PRs that change subagent delegation, async task dispatch, workflow orchestration, reconciliation, or completion plumbing.

These changes often look safe in unit tests while silently dropping a capability or hook on one call path. Review the full data flow, not just the modified function.

## What to verify

1. **Capability boundaries stay authoritative**
   - First identify which layer owns child capabilities. In Hermes delegation, the parent/configured delegation path is normally the authority; a model-facing per-node override can replace or widen that boundary rather than “preserve” it.
   - Confirm every child still receives the intended inherited/restricted capabilities through the established delegate path.
   - If a node field such as `toolsets` is removed, check both the schema and stale-client validation. Removal is correct when it prevents workflow-authored nodes from overriding the parent boundary; it is a regression only when the field was an intentional supported contract with equivalent safety.
   - Roles, permissions, credentials, workdirs, and approval behavior need the same ownership analysis. Do not assume that forwarding more fields is safer.

2. **Background completion ownership survives pruning**
   - A bounded recent-record list is an observability cache, not an authoritative workflow store. Polling only that list can leave a dispatched node stuck forever after eviction.
   - Workflow-owned completion should be consumed at finalization time, before pruning, through a private callback or equivalent owner notification. Keep polling only as a fallback.
   - Invoke owner callbacks outside the async-registry lock to avoid lock inversion. Callback failure must be logged without suppressing the normal completion event.
   - Keep terminal state transitions monotonic. A late success or error callback should apply only when the node is still `dispatched` and still owns that delegation ID; it must not overwrite a manual `record_result`, cancellation, or other terminal state. Test both late-success and late-error arrival after manual terminal recording.
   - Remove callable hooks from public/listed records so serialization and inspection remain safe.

3. **Sibling call paths remain aligned**
   - Compare single-task vs batch flows, foreground vs background flows, and create vs add/dispatch flows.
   - A fix in one branch often needs matching updates in the sibling branch.

4. **Workflow state remains recoverable within its promised durability boundary**
   - Confirm that completed, failed, interrupted, and pruned records can still be reconciled into user-visible state.
   - Distinguish process-local reconciliation from restart durability. A callback can make in-process completion authoritative without making workflow state survive a process restart.
   - Check the fast-completion race: a child may finish before dispatch returns its delegation id. The owner must serialize registration and callback application (for example with the workflow lock) or buffer an early result.
   - Treat dispatch acknowledgement, execution claim, and terminal result as separate states. A CLI or tool that returns after background dispatch must not render missing terminal success as failure, and a `claimed` row is not proof that execution started. Verify durable `running`/terminal transitions plus owner liveness; after owner death, reconcile unfinished claims to an explicit `unknown` state rather than success, deletion, or indefinite `running`.
   - Long-lived services must not inherit process-local child-scope markers from the agent that launches them. Review persistent launchers for delegation/session environment leakage, strip only transient child markers at the service boundary, and verify through a fresh process tree before exercising scheduler-owned work.
   - If a node or record is evicted, make sure the remaining source of truth is still sufficient.

## Review workflow

1. Read the PR intent and identify the end-to-end behavior it is supposed to preserve.
2. Trace all entry points that reach the changed code.
3. Search for every caller of the modified helper or field.
4. Identify the capability owner before judging removed or forwarded fields. Treat model-authored overrides as a security/design decision, not automatically as lost expressiveness.
5. Trace finalization order: record update → callback snapshot → pruning → normal event publication. Check locks and the early-completion race.
6. Look for hidden regressions where a feature is replaced with a stricter validation rule instead of being preserved, but also for hidden widening where an orchestration schema bypasses inherited restrictions.
7. Prefer blocking findings only when you can point to a concrete widened boundary, lost supported capability, broken contract, or unrecoverable workflow state.

## Common pitfall

A patch can improve observability or cleanup while still regressing the product if it removes a user-facing capability from the runtime surface. For example, dropping per-node tool selection, completion callbacks, or reconciliation metadata is a blocker unless the new design preserves the same expressiveness somewhere else.

## Good evidence

- exact file/line and call path;
- a concrete input that now fails or loses capability;
- the caller that still expects the removed behavior;
- a smaller fix that preserves the feature while keeping the improvement.

## Linked notes

- See `references/pr-review-capability-regressions.md` for a compact example of the kind of regression this skill is meant to catch.
