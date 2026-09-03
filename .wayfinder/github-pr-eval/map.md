# Wayfinder Map: Robust GitHub PR Workflow Evaluation

## Destination
Make Agent Signal's evaluator reliable enough to decide whether a GitHub PR workflow instruction should be promoted without confusing prose omissions, judge-order variance, or route mismatches with actual behavior. A promoted candidate must repeatedly choose the correct operational state transitions on frozen replay, adversarial, near-miss, and unrelated held-out cases while the active skill remains unchanged until admission.

## Scope
- In: schema-v3 structured decision receipts; deterministic critical checks; criteria-level semantic judging; winner/criterion disagreement detection; observed Codex model/reasoning attestation; bounded stability admission; regression tests; a frozen PR-workflow suite and candidate; conditional live Hermes promotion.
- Out: changing Hermes approval mode, adding routine multi-agent implementation, scheduling GitHub activity, modifying unrelated active Wayfinder work, rewriting legacy schema-v2 evaluation semantics, publishing or pushing Agent Signal changes.

## Evidence inspected
- `tools/eval.py`: schema-v2 judges return one global `hard_pass`; `judge_disagreement` compares only winners; any false candidate bit rejects admission.
- `tools/eval.py`: direct Codex previously recorded requested reasoning without forwarding it; the current local fix and regression test now pass `model_reasoning_effort`.
- Repeated frozen evaluations: candidate preference and hard-pass varied across runs because answers omitted or judges reinterpreted incidental prose requirements.
- Codex CLI `exec --help`: native `--output-schema`, explicit model, ephemeral sessions, and config overrides are available.
- `.wayfinder/map.md` and `.wayfinder/answer-key.md`: owned by a separate active control-plane effort; preserve them unchanged.
- Working tree: many concurrent unrelated modifications; touch only files explicitly owned by this effort.

## Decisions
| ID | Decision | Rationale | Evidence/owner | Answer-key IDs |
|---|---|---|---|---|
| D-PR-001 | Add schema-v3 behavior as an opt-in extension; preserve schema-v2 semantics. | Existing result consumers and suites must not silently change. | `evals/schema.json`, `tools/eval.py` | AK-PR-001, AK-PR-002 |
| D-PR-002 | Require a fixed structured decision receipt for v3 cases and check critical outcomes deterministically. | Safety/state-transition correctness should not depend on judge prose interpretation. | Failed PR gate runs | AK-PR-003, AK-PR-004, AK-PR-005 |
| D-PR-003 | Judge only noncritical semantic quality per criterion with answer evidence. | A global hard-pass bit conflates omissions with behavioral failure. | `judge_prompt`, `map_judgment` | AK-PR-006, AK-PR-007, AK-PR-008 |
| D-PR-004 | Treat winner or criterion-pass disagreement as explicit instability. | The current report hides hard-pass disagreement when winners match. | aggregation lines 612-645 | AK-PR-009, AK-PR-010 |
| D-PR-005 | Attest the observed Codex model/provider/reasoning and fail the harness on mismatch or missing observation. | Requested configuration is not evidence of the executed stack. | direct Codex stderr metadata | AK-PR-011, AK-PR-012 |
| D-PR-006 | Use a bounded stability contract in addition to the confidence sequence. | Small high-risk suites need transparent finite acceptance, not a false statistical-proof claim. | prior one-trial inconclusive reports | AK-PR-013, AK-PR-014 |
| D-PR-007 | Freeze suite and candidate outside live discovery; promote only the exact evaluated hash after every required check passes. | Prevent evaluation contamination and accidental live self-modification. | capability admission rules | AK-PR-015, AK-PR-016, AK-PR-017 |
| D-PR-008 | Do not add dependencies or persistent evaluation sessions. | Keep the harness portable and avoid session clutter. | user constraints, existing lifecycle | AK-PR-018, AK-PR-019 |

## Constraints
- No edits to the existing top-level Wayfinder files or unrelated dirty files.
- No live PR-skill mutation before an `admit` result for the exact candidate and suite hashes.
- No secret or credential material in receipts, reports, prompts, or fixtures.
- Direct Codex runs remain ephemeral and read-only.
- Critical receipt fields use finite enums; free-text rationale cannot override them.
- Frozen checks may not be weakened after implementation begins. Only status/evidence fields in the answer key may change.

## Failure modes and recovery
| Failure | Required behavior | Recovery/rollback |
|---|---|---|
| Structured receipt is malformed or missing | Deterministic candidate failure with exact path/reason; no semantic judge can override it. | Fix candidate or case prompt; do not promote. |
| Observed model/reasoning differs from requested | Mark harness failure, preserve report, no behavioral conclusion. | Correct route and rerun exact artifacts. |
| Judges disagree on winner or a criterion | Record disagreement and block stability admission. | One bounded fresh-seed rerun; remaining instability is inconclusive. |
| Candidate loses or misses any critical outcome | Reject and leave live skill unchanged. | Rework frozen candidate; do not weaken checks. |
| Legacy v2 regression | Stop implementation. | Revert v3 code while retaining the prior reasoning-forwarding fix. |
| Evaluation process is interrupted | Durable partial report and no retained session/process. | Clean temporary state and rerun only if artifacts remain hash-identical. |

## Dependencies and sequencing
1. Freeze this map and answer key.
2. Add red tests for schema-v3 receipts, per-criterion judgments, disagreement, attestation, and stability decisions.
3. Implement minimal backward-compatible evaluator changes.
4. Pass targeted and full repository verification.
5. Freeze candidate and five-case suite before model calls.
6. Run bounded multi-seed direct-Codex evaluation with observed attestation.
7. Promote only the exact evaluated candidate on complete admission; otherwise restore/retain baseline.
8. Verify live discovery and clean disposable artifacts.

## Design direction
Schema v3 separates three layers: (1) native-schema constrained decision receipts, (2) deterministic checks for critical operational state, and (3) blind criteria-level comparison for rationale quality. Route attestation and strict stability are independent gates. The evaluator reports deterministic failure, semantic loss, judge instability, and harness failure as different outcomes. Existing schema-v2 suites keep their current behavior.

## Blockers
- None. Direct Codex is authenticated and supports the required ephemeral/output-schema route.
