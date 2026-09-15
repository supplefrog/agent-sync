# Live Desktop probes and generated-session cleanup

Use when validating Hermes Desktop behavior that may route, branch, delegate, compress, or create visible sessions.

## Select the session operation before testing or repairing it

1. Load `session-librarian` and its `references/desktop-session-api.md` for operation selection, authentication, route pins and exact readback. Recheck source only when that recipe conflicts with the installed contract; an unrelated helper's failure does not justify another API repair.
2. For a fresh coordinator, carry the current outcome, authorization, changed controls, evidence pointers and next task—not the old transcript or stale task list.
3. Distinguish backend activation from a clean conversation context. An existing session recipe is not permission to run extra live probes.

A user-authorized session operation is not itself a request for another API repair, routing benchmark or admission campaign. Investigate only a reproduced failure of the requested operation.

## Before a live probe

For staged skill edits, first use a fresh process with a probe-local `HERMES_HOME` and `skills.external_dirs` pointing only to the staged tree. Confirm discovered names, returned source paths and content without changing live discovery. Load nested reference packages through `skill_view(owner, file_path="references/.../SKILL.md")`, not as standalone names. Cover an ordinary load, unknown name and traversal refusal. Loader compatibility does not prove natural triggering or model quality; these checks need no inference or visible test session.

1. Inspect existing sessions and prior evidence. Do not rerun a cross-thread smoke because its result is absent from the current context.
2. Treat session-list changes as user-facing side effects. Get explicit approval before a probe can create, route, branch, or delegate into another visible session.
3. For a behavior change, use existing logs and the cheapest check that exercises the changed boundary. Do not substitute option-setting tests for the reported UX outcome, or add a test campaign before an ordinary supported operation.
4. Make the probe bounded and non-delegating: no whole-repository audits, broad research, implementation work, or prompts likely to spawn workers. Prohibit tools and delegation when they are not under test.
5. Record the origin and every destination/child ID when created. Submit once; after an ambiguous submit, read live state before any retry.

## If fan-out occurs

1. Stop submitting immediately and disable the routing or middleware surface.
2. Stop active turns or restart Desktop before deleting sessions. Deleting an active parent does not terminate its worker; the worker may recreate records or spawn children.
3. Inspect the authoritative session DB after shutdown. Prove the cleanup set from ancestry, timestamps, first user instructions, and source/model metadata; never delete by title alone.
4. Preserve real user sessions. Delete only reviewed disposable IDs with the supported session CLI; delete children before parents when practical.
5. Verify the IDs are absent, then verify the sidebar and composer. A stale null end time after restart is transcript metadata, not proof of a live worker; inspect processes separately.
6. Treat outputs from an accidental smoke workload as contaminated. Do not use them as findings or admission evidence.

## Choice-card fallback

If the user reports that a clarify/choice card is not visible, do not issue the same card repeatedly. Mirror the choices in plain text with the recommended option first, preserve the original wording and distinctions, and accept a short reply such as `recommended` or the option number. The card is progressive enhancement; the decision must remain usable without it.

## Admission

Operational UX is part of the gate. Correct routing that pollutes the live session list is a failed admission. Keep the capability disabled and unadmitted, record the failure, and require a redesigned bounded probe instead of repeating the workload.
