# Evaluator Process and Evidence Lifecycle

Use this reference for long-running capability, instruction-retirement, and cross-host evaluation lanes.

## Run ownership

- Give every physical admission episode a unique run ID, raw-report path, attempt ledger, and bounded budget before launch.
- Do not reuse a mutable report path across an interrupted attempt and its retry. A surviving stale process must be unable to overwrite current evidence.
- A terminal tab, launcher wrapper, or background handle ending is only a cancellation request. It does not prove the evaluator or its model-call descendants ended.
- Before retrying, enumerate from the recorded native process identity and prove the whole descendant tree is inactive. Unknown liveness fails closed and blocks relaunch.
- Count every observed physical model attempt from completed, interrupted, discarded, retried, and orphaned runs against the original episode cap. Never infer attempt count from the wrapper state or one visible session alone.

## Cancellation and cleanup

1. Persist the current run identity and known native handles before requesting cancellation.
2. Use the host's authorized process-tree cancellation boundary when available.
3. Re-read process-tree state and evaluator-created session state. A surviving descendant means the run is still active.
4. Delete only exact evaluator-owned sessions after preserving the required report or failure receipt.
5. If overlap, report-path collision, unknown liveness, or cap overrun occurred, classify the whole episode as harness-invalid. Do not reinterpret partial case scores as behavioral evidence.

## Evidence boundary

- Keep prompts, model outputs, route/session receipts, and machine-local paths in an ignored or access-controlled raw report.
- Hash the raw report after terminal state and cleanup are durable.
- Publish a compact summary containing the raw SHA-256, artifact hashes, exact stack, decision rule, physical-attempt totals, case outcomes, verdict metrics, and lifecycle counts.
- Do not publish raw prompts/outputs, session IDs, credentials, user-home paths, or multiline runtime diagnostics. Reduce version fields to the public version/revision line.
- A historical summary may preserve recorded artifact hashes after the candidate or harness evolves, but must label them `recorded-hashes-only`; it must not claim current-file validation.
- Cross-host aggregates should hash the raw host reports, while each public host summary exposes the matching raw-report hash.

## Acceptance probes

- Cancel the wrapper while a child is live; acceptance requires detecting the surviving descendant and blocking relaunch.
- Attempt two runs aimed at one output path; the second must fail closed or receive a distinct run-owned path.
- Interrupt after at least one model call; cumulative budget accounting must include it.
- Place an escaped Windows home path and a session ID in a synthetic raw report; the public summary must omit both while retaining counts and the raw hash.
- Verify that malformed or stale recorded hashes cannot be presented as current artifact validation.
