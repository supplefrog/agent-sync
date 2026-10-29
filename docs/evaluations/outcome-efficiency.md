# Outcome and token eligibility integration

Future skill-value and retirement decisions follow the [governing claim-based testing contract](../system-requirements.md#claim-based-testing-and-retirement). Its claim relevance, independent failure sensitivity, predeclared comparability and whole-job accounting requirements are additional to the consistency checks described below. Existing quality-only retirement or schema-valid receipts do not by themselves establish those requirements. New `eval.py` launches also require each case's `acceptance_review`: named reviewer; `assertions` covering actual check IDs exactly once with `requirement`, `constraint` (`invariant`, `required_interface`, `safety`) and `justification`; and risk-selected `controls` with unique `id`, `output`, expected `deterministic_pass`, reviewed `outcome` (`adequate` or `broken`), boolean `alternative`, and `rationale`. Supply an adequate alternative or explain `alternatives_not_applicable`. Check IDs are `criteria:N`, `must_contain:N`, `must_not_contain:N`, `semantic_criteria:ID`, `receipt_schema`, and `expected_receipt:PATH` where present. The preflight reuses the actual deterministic checker, blocks mismatches before runtime creation and records results in the report. It cannot authenticate the reviewer, prove the cited requirement entails an assertion, establish semantic adequacy or prove variant coverage. A broken semantic control may pass deterministic checks; its detection remains a reviewer/judge responsibility, never an automatic preflight pass claim. The suite and harness hashes freeze these inputs; actor/judge prompts do not receive control answers. Historical report readers do not impose this new-launch gate retroactively. Valid comparable outcomes without a skill require a retirement decision; missing/underpowered evidence is inconclusive. This text does not change historical results or implement a new automatic retirement gate.

The changed-instruction check in `tools/instruction_changes.py` still binds the
current profile, exact source bytes, suite, prompt snapshots and current harness.
`tools/evaluation_evidence.py` now permits equal outcomes as well as quality wins,
conditional on full declared case/trial coverage, no recorded regression, and
equal or fewer overall tokens for every matched task. Existing report decisions
are still recomputed: a quality tie need not be mislabeled a quality win.
Sequential comparisons use the recomputed complete trial count within their
declared minimum/maximum and stopping rules; v3 retains its exact stability plan.

Accounting reuses `tools/evaluation_measurement.py` and
`tools/evaluation_usage.py`, copied byte-for-byte from the staged measurement
workstream. Retries and recurring supporting calls count; duplicate invocations
are counted once, conflicting duplicates fail, and missing coverage, route,
prerequisites, source binding or effective tool-schema evidence blocks eligibility.
Shared judges need explicit arm attribution. Both modules are included in
`tools/artifact_hash.py` harness binding.

The result is recorded-evidence consistency, never execution authentication,
semantic oracle adequacy, or fresh behavioral proof. Synthetic fixtures exercise
the policy; replaying recorded runs does not create a new model trial. A passing
helper alone does not admit a native artifact-pilot report: that producer's
`admission: false` remains intact. The existing source-bound measurement path
recognizes `native-skill-study` reports and returns diagnostic validation with eligibility
false. A native publication/admission contract is not implemented. The legacy inline lane
still cannot establish tool-dependent program behavior; aggregate Codex counters
do not establish complete overall usage. No existing skill is newly admitted.

Focused regressions are in `tests/test_outcome_efficiency.py` and
`tests/test_instruction_measurements.py`. The latter confirms that a quality win
with missing overall usage is now excluded at the actual sync boundary. The
quality-recomputation and retirement tests retain their separate decision rules.

This is a staged local mechanism change. No authoring experiment, live inference,
publication, sync, deployment, installation or permission change was performed.

`validate_artifact_evidence` in `tools/evaluation_evidence.py` reuses the existing
artifact observation projection and usage checks. It checks plan/result coverage,
package identities, prepared catalog/fixture manifests, raw outcome consistency,
and saved projection drift. Its optional SHA256-to-bytes map independently binds
explicitly supplied package, fixture, final-artifact, oracle, harness and native
implementation bytes; it never opens recorded paths or runs an oracle. Package
identity uses the same `tools/artifact_hash.py` helper as the actual freezer.
Consistent failed task receipts remain negative evidence, not malformed successes.

The recorded real program pair rechecks consistently, with 46 of 48 declared
source bindings matched against retained public code and the exact current native
implementation bytes matching the eight recorded file fingerprints in both arms.
Those fingerprints cover the accounting implementation files, not the complete
native host, tools and dependency closure.
Missing byte bindings are the two assembled native prompt bodies. The catalog's `prompt_sha256` hashes the assembled system
prompt; it does not hash the user task. The raw records lack a separately recorded
user-task input hash and complete instruction-source-to-request attribution.
Hash matching cannot authenticate execution or establish oracle adequacy. Native
before/after instruction admission bindings, the current profile/acceptance task
contract, and required acceptance trials/workflow coverage remain separate gaps.

`tests/test_native_artifact_evidence.py` covers positive recorded consistency,
missing/wrong bytes, authority relabeling, corrupted projections, coverage,
catalog/fixture drift, failed task receipts and path-safe validation without I/O.
`tests/test_instruction_measurements.py` verifies that the actual source-bound
eligibility path returns the native diagnostic and still refuses admission.


## Consolidation capability boundaries, 2026-10-20

The independently reviewed oracle contract passes 86 offline regressions; the initial combined local source candidate passed 155 offline regressions; after collection/runtime interface integration the candidate passes 232 offline regressions. These are mechanism checks, not new model trials or skill-quality evidence. Semantic assertion relevance, adequate alternatives and practical significance still require responsible review. Historical scores and separate postcapture adjudication retain their original scope.

The completed reviewed-host collection/runtime interfaces are integrated with the newer oracle checks; their native model runs remain source-bound historical observations and do not automatically qualify or replace this canonical lane. The isolated adaptive dispatcher has 24 offline registry tests and eight representative synthetic calls, but no native actor assembly or returned role-tool/provider-request exposure was observed. Its model gate remains closed. Private profiles and global tool registration are outside this consolidation. Shunt/Luna and R21/R22 remain incomplete.

This evaluator has no integrated screenshot/motion review, browser functional acceptance or blinded visual judging. Inline judges receive text. It cannot fairly decide frontend visual skill value from these lanes; a text or code pass is not that evidence. No frontend implementation is added here.


## Completed product outcomes and supplied judgment

The offline artifact-pilot entrypoint can join supplied final artifacts, stated
product-goal/intervention/actor citations and an existing human rendered assessment:

```bash
python tools/evaluation_artifact_pilot.py review-input --input-report REPORT.json --operator-input INPUT.json --out FRESH_DIRECTORY
```

INPUT.json selects outcome_packet, sources_root and sources_manifest. Each manifest
member must remain inside that explicit source root and match its digest; the
source bundle is bounded to32MiB without truncation. The consumer checks actual
result/capture/mapping/assessment bindings and rejects coherent alias or assessment
substitution. It does not launch an actor, infer a missing goal, authenticate a
human, establish blind conduct or treat preference as finished-product adequacy.
The supported rendered format is a retained two-view, three-result judgment with
one shared current output; other formats remain unsupported.

The existing attach-review CLI route consumes an explicit completed attachment and
source bundle into a fresh successor report. Native-study attachment requires its
bound input plan. Raw captured assessment is preserved separately from completed
review. A valid negative or partial result remains negative/partial; unknown task
fitness or usage is never upgraded or counted as zero. Quality preference and
legacy efficiency remain separate, with deployment/adoption authority false.
This offline consumption is not a new comparison or automatic instruction release.
Keep any private assessment/source material outside the public repository; source
publication includes the consumer, not the supplied human records or artifacts.

The completed-outcome source path uses the existing published usage APIs.
Their required HOOKS/reconcile_program_usage definitions and TOKEN_KEYS/counter/seconds
dependencies are unchanged; native observer/request-path upgrades remain separate
source work and are not implied by shipping this offline result consumer.
