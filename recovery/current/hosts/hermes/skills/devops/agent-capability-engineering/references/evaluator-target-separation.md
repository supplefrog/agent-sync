# Separate evaluator failures from target failures

Use when a harness, benchmark, evidence gate, or acceptance runner reports that an agent/runtime violated a capability contract.

## Three independent claims

Keep these separate:

1. **Target behavior** — what the runtime emitted, persisted, or changed.
2. **Evaluator behavior** — what the harness consumed, transformed, timed out on, or classified.
3. **Expected contract** — what authoritative source, types, or product semantics require.

An upstream defect exists only when the target observation violates the supported contract after the evaluator is validated.

## Procedure

1. Preserve raw events, persisted records, artifacts, exact versions/commits, and timestamps before changing the evaluator.
2. Inspect the target's authoritative type/status vocabulary and lifecycle semantics. Do not invent terminal labels or infer task completion from process/session state.
3. Parse structured data structurally. Never use whitespace-sensitive grep, regex over source-shaped JSON, enumeration counts, or source text as behavioral authority.
4. Separate nearby outcomes: artifact production, delegated-task completion, child/session termination, result delivery, persistence, and model instruction-following.
5. Unit-test the evaluator with fixtures for every observed valid shape, including compact serialization, fallbacks, pre-terminal states, and exact terminal values.
6. Prove the evaluator test bites with a genuinely failing target record.
7. Re-run the same production-seam probe against the exact baseline and, when relevant, the exact head of an existing fix PR. Preserve separate commit/image receipts.
8. Classify the result narrowly: for example, “artifact succeeded; task remained nonterminal,” “terminal state arrived; parent delivery absent,” or “model omitted explicit reply; runtime fallback succeeded.”
9. Only then change the contender verdict or file upstream. If an open PR already owns the bug class, contribute there rather than opening a duplicate mainline PR.

## Effective-stack and rubric integrity

- Treat reported model, provider, reasoning, tool, prompt-assembly, and context settings as assertions until the actual child command, environment, or request proves they were applied.
- When a harness exposes a setting, add a command-construction or request-capture regression test showing the adapter forwards it. A result produced under a different effective stack is harness evidence, not target evidence.
- Hard criteria should test the candidate delta and the scope the prompt actually asks the model to address. Do not fail a focused answer for omitting an unchanged downstream invariant unless the task explicitly elicits it.
- If order-swapped judges agree on the preferred arm but disagree on hard-pass completeness, classify evaluator uncertainty separately from target regression. Do not tune durable instructions merely to force every valid answer to enumerate the rubric.
- Keep admission fail-closed: an unstable or rejected candidate is rolled back. Preserve the harness fix and failing fixture, but do not average away hard failures or promote from metadata-only equivalence.

## Robust semantic admission gates

When an instruction or agent-capability comparison needs model judgment, make the gate prove its own discrimination before it can promote anything:

1. Require a machine-readable receipt for each arm and validate critical invariants deterministically before semantic judging. Keep receipt failure distinct from a judge preferring the other arm.
2. Present candidate and baseline through identical anonymous framing. Use order-swapped judges and preserve every raw vote; arm labels, filenames, and prompt differences must not leak identity.
3. Calibrate the exact harness and effective stack with three controls: an A/A comparison that must not admit, a known-effect candidate that must admit, and a known-degraded fixture that must fail at least one critical receipt. A harness that misses any control is not promotion evidence.
4. Attest requested versus observed host, provider/transport, model snapshot, reasoning, prompt assembly, tool policy/schema, runtime, and seed/trial settings from the executed child command or request. Fail closed on an unattested or mismatched route.
5. Use bounded multi-seed stability criteria. Critical receipts must pass on every configured seed; admission requires no losses, no unresolved disagreements, and wins in predeclared representative and held-out kinds. Ties may document nondiscriminating cases but cannot satisfy a required win.
6. If the initial order-swapped judges disagree, one predeclared bounded third judge may resolve the same frozen outputs by strict majority. Record both the raw disagreement and its resolution; an unresolved split blocks admission.
7. Keep a fresh confirmation suite separate from the cases used to tune the candidate or rubric. Preserve exact candidate, baseline, suite, harness, and effective-stack hashes so the promoted artifact can be checked byte-for-byte or by the repository's canonical artifact hash.
8. Preserve backward compatibility for older suite schemas explicitly. New receipt or attestation requirements should be additive or version-gated, never silently reinterpreted as evidence old suites did not collect.
9. Clean evaluator-created sessions, processes, and disposable workspaces after durable reports are written, then verify absence. Lifecycle cleanup is part of the gate, not optional housekeeping.

## Pitfalls

- Treating the evaluator's error message as direct evidence about the target.
- Fixing the evaluator until the candidate passes without retaining a known-failing fixture.
- Conflating resident agent status with delegated-task status.
- Treating model instruction noncompliance as a deterministic runtime defect.
- Treating shutdown fallback as proof of normal live delivery, or vice versa.
- Comparing baseline and PR builds without exact identities.
