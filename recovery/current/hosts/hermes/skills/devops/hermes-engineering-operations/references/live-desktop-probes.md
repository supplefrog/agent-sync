# Live Desktop probes and generated-session cleanup

Use when validating Hermes Desktop behavior that may route, branch, delegate, compress, or create visible sessions.

## Before a live probe

1. Inspect existing sessions and prior evidence. Do not rerun a cross-thread smoke because its result is absent from the current context.
2. Treat session-list changes as user-facing side effects. Get explicit approval before a probe can create, route, branch, or delegate into another visible session.
3. Prefer deterministic tests and logs. A live probe is an admission gate, not a substitute for unit coverage.
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
