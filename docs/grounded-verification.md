# Independent grounded verification

## Decision

Adapt the existing Agent Signal evaluation owner with a small contract and deterministic validator. Do not install or make make-no-mistakes, VNVSPEC, GroundEval, or another framework authoritative.

This is a reversible extension of `tools/eval.py` and `tools/eval_gate.py`, not a second evaluation system. The existing harness still owns matched baseline/candidate trials and cross-host aggregation. `contracts/grounded-verification.schema.json` and `tools/grounded_gate.py` add the missing admission boundary: frozen user intent, role separation, access receipts, independent deterministic re-execution, falsification probes, negative controls, teeth testing, and world-state evidence.

## Outcome contract

A material result is trusted only when:

- user-sourced criteria are frozen before implementation, the original hash and complete amendment event IDs/final hash are sealed in a receipt whose digest is supplied by the verifier outside the mutable contract, and amendments form a complete intent-owner decision chain from that trusted root to the current criteria;
- intent, specification, test design, implementation, oracle, and verdict have distinct opaque principals and contexts;
- a typed test-author receipt whose digest is independently supplied by the verifier binds the exact frozen timestamp, externally trusted original criteria hash, final decision-chain hash, test-author principal/context, and independent output digest; test authors receive only that frozen intent/specification, while implementers cannot read or edit held-out tests, oracle logic, rubrics, or gate recipes;
- the verdict owner re-executes every trusted deterministic check and supplies independent falsification probes;
- every trusted gate demonstrates a negative control;
- every material code path has property or metamorphic coverage and mutation or equivalent teeth evidence where supported;
- open-ended outcomes use cited world state rather than an LLM judge when the state is machine-checkable;
- every material criterion maps exactly once to an immutable decision scope, each scope declares required evidence lanes and verdict gates, and a narrow passing candidate receipt cannot inflate into comparison, architecture, or promotion authority;
- isolation is reported at its actual strength. A fresh chat or model behind the same visible proxy is not full independence;
- false positives, false negatives, runtime, model/context cost, maintenance, Windows portability, and host neutrality are explicit.

Verification asks whether the implementation satisfies the frozen specification. Validation asks whether that specification still represents user intent. The implementation or specification author cannot issue the final verdict.

## Candidate comparison

| Option | Mechanism | Local defect detection | Total burden | Portability | Decision |
|---|---|---:|---|---|---|
| Retain/no-change | Keep current matched trials, blind judging, hard checks, hashes, and host aggregation | Missed principal ownership, criteria freeze, access isolation, negative controls, and oracle strength; the human-off candidate was green before independent lifecycle review | Lowest | Existing Windows/host support | Reject: known false negatives remain |
| Adapt current owner | Add one JSON contract, validator, sealed freeze/test-author receipts, negative fixtures, property/metamorphic and equivalent-teeth checks; retain current eval runners | Detects all 16 preserved human-off blockers and preserves the routing-specific non-regression | Small, no daemon/package/framework | Python + JSON; host-neutral and Windows-tested | Select: smallest reversible positive-net-value option |
| Replace with external framework(s) | Install make-no-mistakes hooks/gates, VNVSPEC traceability, or GroundEval state evaluators | Mechanisms are promising, but no candidate was independently reproduced against this repository and all add infrastructure or narrower assumptions | Highest and unmeasured | make-no-mistakes includes host hooks; VNVSPEC is Python/CI-oriented; GroundEval targets stateful evidence paths | Reject for now: upstream claims are hypotheses, not local admission evidence |

Useful techniques are adapted without adopting their framework owners:

- make-no-mistakes v0.13.0: frozen specs, tamper receipts, negative controls, independent re-execution, and mutation gates. Canonical repository is MIT licensed, but its own tests and README claims are not independent local proof.
- VNVSPEC 0.3.2 / pytest-vnvspec 0.2.0: typed requirements, evidence records, trace graphs, and explicit inconclusive coverage. arXiv:2607.17686 is a preprint whose self-application results remain unverified here.
- GroundEval, arXiv:2606.22737v2: deterministic state, access, temporal, and trajectory oracles. It is a preprint and its claims remain unverified here; the portable idea used here is only to prefer machine-checkable world state over judge prose.
- Property/metamorphic checks test invariants across transformations; mutation or equivalent teeth checks prove the gate can reject a load-bearing fault. These are techniques inside the current owner, not new authorities.

NASA's IV&V overview distinguishes verification (building the product right) from validation (building the right product) and defines technical, managerial, and financial independence. This local contract can enforce technical and context/workspace separation, but it must not claim organizational or financial independence that an agent workflow does not possess.

Primary sources:

- <https://www.nasa.gov/ivv-overview/>
- <https://github.com/momomuchu/make-no-mistakes/tree/v0.13.0>
- <https://arxiv.org/abs/2607.17686>
- <https://github.com/ai-vnv/vnvspec>
- <https://arxiv.org/abs/2606.22737>

## Pilot

The source acceptance contract is `kanban:t_1e0d8e90`; `kanban:t_67bb4407` is only the preserved routing pilot subject. The verifier-rooted receipt preserves the original freeze and binds the complete amendment chain. `DEC-001` adds the board regression, `DEC-002` rejects scope inflation, `DEC-003` adds evolving intent/summary/research-first/no-reminder requirements, and `DEC-004` adds legacy reclassification, ultimate-agent/Prime evidence boundaries, and the fleet omission. The gate detects:

1. a stale route receipt after supported mutation;
2. absent real per-surface evidence;
3. declarative-only cross-surface enforcement;
4. unreconciled delivery/worktree state; and
5. the native cc lifecycle boundary (23 pass, 6 fail, 1 error);
6. failure to proactively surface review-blocked/no-promotion state; and
7. failure to reconcile or escalate ready work assigned to a nonexistent principal;
8. loss of evolving multi-turn intent lineage;
9. a generated summary overwriting authoritative lineage;
10. omitted research-first sequencing or cross-host resume continuity;
11. material status that required a user reminder;
12. the second-reminder summarizer/intake omission;
13. legacy done status treated as verification evidence;
14. an ultimate-agent convergence claim without fresh cross-host evidence;
15. an optional Prime claim without persistence, lifecycle, safety, Kanban, rollback, and Windows evidence; and
16. the third-reminder fleet omission.

It separately records the later route receipt-invalidation fix as a non-regression. Deterministic board/event evidence keeps ready work classified as ready, rather than running, and catches the proactive-status and phantom-assignee omissions without relying on the implementing agent's narrative. This avoids blaming the exact-route patch for pre-existing native lifecycle incompatibility while still blocking promotion under the source acceptance contract.

Public-safe fixtures are under `evals/fixtures/grounded-verification/`. The amended frozen black-box test-author prompt ran in a separate temporary workspace with only the `todo` tool; it had no implementation, file, terminal, web, rules, or repository access. `independent-test-author-receipt.json` binds the JSON output to the contract ID, test-author principal/context, exact `frozen_at`, trusted original criteria hash, final decision-chain hash, complete criterion IDs, artifact path/digest, input scope, output type, and denied implementation access. The contract separately digest-binds both receipt and output; stale or mismatched substitutions fail validation. The implementer-authored validator cannot certify itself: the verdict requires a separate verifier context to rerun the deterministic suite and falsification probes.

`S-VERIFICATION` covers implementation/specification verification. `S-ADOPTION` covers the broader candidate comparison and requires baseline, candidate-trial, cost, maintenance, portability, host-neutrality, and rollback lanes. `S-INTENT-LINEAGE` requires multi-turn lineage, summary non-authority, research-first resume, proactive status, and second-reminder evidence. `S-ULTIMATE-AGENT` requires evidence-based legacy classification, convergence revalidation, Prime persistence/lifecycle/safety, fleet omission, Kanban authority, rollback, and an explicit no-downstream-pass-claim lane. The latter verifies gate coverage only; downstream Hermes/Codex/OMP/Prime outcomes remain not evaluated. A terminal child or candidate-trial receipt remains valid only for its narrow lane; omitting any broader lane or `G-PILOT` rejects the claimed scope.

## Run

```bash
python tools/grounded_gate.py evals/fixtures/grounded-verification/valid.json --trusted-freeze-receipt sha256:3868a5160cea5766b95b0dc7d0ce767405851bfd85915b45c0d72799d8a6c4c5 --trusted-test-author-receipt sha256:29eb735dac530fd486a25234879c6b8b090f3cc602299b0b0838ca39b92caa53
python -m pytest -q tests/test_grounded_gate.py
```

The negative fixtures must all fail validation. The valid fixture must pass both JSON Schema and semantic validation.

## Rollback and reevaluation

Rollback is deletion of the schema, validator, fixtures, tests, report, and this document. No live route, plugin, skill, service, or external dependency changes.

Reevaluate external adoption only if a candidate is locally reproduced against the same frozen pilot and beats the adapted owner on defect detection after runtime, context, maintenance, Windows, host, and infrastructure costs are included.
