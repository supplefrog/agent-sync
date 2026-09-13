# Routed artifact pilots

Status: experimental, supervised native-Windows lane. This extends `tools/eval.py`; it is not a replacement evaluator, admission gate, sandbox, or production scheduler.

This runner injects instructions and disables child delegation and normal host discovery. It cannot test a full architecture workflow or naturally loaded baseline. Before any model spend, use the owning `skill-creator` evaluation preflight to match the intended claim to the task and execution surface. Passing runtime checks does not validate an experiment's design.

The inline evaluator still accepts only tool-free text. Use an artifact pilot when the question requires editing and actually exercising a local product. It reuses:

- `artifact_hash.freeze_candidate` for instruction snapshots;
- `evaluation_runtime` for isolated runtime homes and native executable discovery;
- the existing V3 selector, frozen route receipts, exact request guard and native leaf lifecycle;
- a project-owned deterministic oracle, run by the parent after each worker exits.

## Operator contract

Inspect the suite, fixture and oracle before running. All are trusted operator inputs, not untrusted remote jobs. The native terminal/file tools are not an OS sandbox. Separate runtime homes prevent ordinary configuration and session contamination, not adversarial access to neighboring files. Keep fixtures free of secrets and forbid external effects. Do not call procedural path restrictions security isolation.

Use a currently callable route with observed tool capability and a freshly observed subscription quota. No API spend or model fallback is permitted by this lane. Catalogue availability does not establish task quality; unknown costs stay unknown. The provided quota number is an operator observation, not a continuously refreshed balance or a guaranteed quota reserve. A bounded pilot cannot authorize automatic quota resets.

Run from the owning checkout:

```text
python tools/eval.py artifact-pilot prepare --suite suite.json --out pilot-run
python tools/eval.py artifact-pilot run --out pilot-run
```

The suite is JSON with:

- `purpose`: exactly `runtime-smoke` or `injected-instruction-study`. Missing/unsupported purposes fail before preparation or launch. Existing suites without this field are not silently grandfathered; preserve historical evidence rather than relabeling it as a new valid experiment.
- `protocol`, `model`, `reasoning`, `route_id`;
- `max_workers` (1–3), `max_iterations` (1–64), `timeout` (1–600 seconds);
- `quota_remaining` (observed percentage points), `workspace_root`, `oracle`;
- `arms`: objects with unique `id` and an instruction-file path in `instructions`;
- `cases`: objects with unique `id`, fixture-directory path in `fixture`, and organic `prompt`.

A runtime smoke is capped at one trial. An explicitly scoped injected-instruction study permits at most twelve arm/case trials; that label does not establish meaningful task discrimination or natural workflow fidelity. Reports carry the executed purpose and `workflow_comparison_supported: false`. No implicit reruns: a pre-existing plan or trial-output directory blocks duplication. Source, oracle and initial-fixture hashes detect the drift checked by the controller. Preserve the exact executed source alongside reports when code changes afterward; a hash alone is not a recoverable snapshot.

The oracle is a Python script invoked with `FIXTURE CASE_ID`. It returns JSON containing positive integer `passed`, integer `failed`, and a `failures` list. Success requires a zero exit code, at least one passed check, zero failed checks, and an empty failure list. Malformed or inconsistent success output is not acceptance. Challenge the oracle with known-bad and correct reference behavior before candidate work; schema validity alone cannot validate the assertions.

## Parent acceptance and limits

Read every worker result and replay each saved V3 receipt. Check native completion and handle closure, then independently rerun the delivered tests and oracle on disposable copies. Preserve original artifact hashes. For a generated verification helper, execute its documented launch/doctor/drive/cleanup path and a plausible wrong implementation; require failure evidence to survive cleanup.

`report.json` contains exploratory observations only (`admission: false`). A successful native run is distinct from oracle acceptance. Generated instruction packs are explicit projections; they do not prove natural skill triggering or reproduce an entire live host. Cumulative input-token accounting is not billed cost. Concurrent timings and a single trial per cell do not establish reliable speed differences.

The outer timeout is not a process-tree containment guarantee. Do not use this lane for long-lived services or adversarial code. Any timeout, missing report or cleanup failure requires inspecting owned process/state residue before another run; no automated recovery or retry is implemented. Do not promote the lane as an unattended general-purpose executor on the strength of short successful trials.

Tests cover route refusal, exact-route preservation, bounded inputs, frozen-oracle drift, implicit reprepare rejection, malformed-success rejection, secret-bearing failure-output rejection and durable reporting when native close raises. These controls complement, not replace, real native execution and independent artifact verification.
