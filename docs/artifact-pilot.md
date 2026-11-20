# Skill Evaluation

Compare actual files produced with and without a skill under the same model, tools, fixture and limits. Verify that the actor used the tools and read the candidate entrypoint. Run the independent oracle on each final file set, then review the outputs against the frozen task criteria. A tooling check or a successful oracle run alone cannot establish that a skill improves the work.

## OMP file trials

The `omp-artifact-study` runs two to four arms on stock OMP via stdio RPC. The control has no optional skill. Each treatment has one frozen package explicitly selected for discovery in a fresh project catalog. All arms use `read`, `write`, `edit`, and `bash` and the identical user prompt. The worker checks the native model/provider/effort, catalog, tool schema, tool start and completion, complete skill-entry reads, ephemeral session completion and file changes. Numbered reads or verbatim ranges are checked against the frozen entry. The controller records per-arm file hashes, oracle evidence, wall time and observed token records. Review the model-visible output files for semantic quality. The runner covers local text artifacts and a leaf task. Use reviewed packages and fixtures with no external side effects. Run untrusted packages in a supported OS sandbox.

### Reproduce the handoff comparison

Use an Agent Sync environment with its Python dependencies and OMP 18.22.1 on `PATH`. The case uses a supplied customer-trial packet and asks for a reusable skill plus a worked handoff. The three candidates are the current `skill-writing`, Anthropic's unmodified Skill Creator, and Agent Sync's adapted Skill Creator. The historical blind A and B artifacts are the positive oracle controls. The input-only tree is the negative control.

```sh
git clone https://github.com/anthropics/skills .staging/anthropic-skills
git -C .staging/anthropic-skills checkout e4bb5d960d87126ff3b3a8af1a104b7db67560ba
python evals/fixtures/native-skill-study/skill_creator_suite.py \
  --run .staging/handoff-study \
  --upstream .staging/anthropic-skills/skills/skill-creator/SKILL.md \
  --model gpt-6.2-sol
python tools/run.py eval artifact-pilot prepare \
  --suite .staging/handoff-study/suite.json --out .staging/handoff-study/results
```

For an offline check, run `python evals/fixtures/native-skill-study/omp_loopback_check.py .staging/handoff-study`. Its deterministic replies exercise stock OMP tools and write known reference files. They provide no model-quality comparison. Use a separate fresh run directory for a live study and supply `--observed-quota` with the current subscription quota percentage when generating its suite. The live runner requires the selected provider's native OMP OAuth login and never switches providers or uses API keys.

```sh
python tools/run.py eval artifact-pilot run --out .staging/handoff-live/results
```

To exercise the bundled grading, benchmark and revision viewer offline, run `python evals/fixtures/native-skill-study/skill_creator_review_check.py .staging/handoff-review-check`. It checks a deliberately missing file and its corrected successor. Review outputs are written as static HTML.

## Package QC

Run NVIDIA SkillEvaluator 1.0.1 on each candidate package before live trials. Create the report directory, then run these keyless checks:

```sh
skillevaluator tier1 "$skill_dir" --no-llm --checks schema,license,unicode,quality,lint,harness \
  --policy evals/nvidia-tier1-policy.yaml -r json -o "$report_dir"
```

Use structural failures to catch invalid packages and review the weighted quality score and harness findings as advice. The policy keeps the optional Markdown title advisory. OMP loaded the legacy heading-free package, and the policy still failed a control package with its required description removed. The selected checks cover package structure, licensing, Unicode, quality, script lint and versioned harness profiles. Use the applicable security, PII and dependency checks for those claims. Check OMP discovery and tool use in the live trial. Use NVIDIA's isolated Tier 3 trials when they support the chosen harness and authorized model route.

Fleet Admission (`tools/eval_gate.py --suite SUITE --candidate SKILL.md --required-host HOST ...`) revalidates the exact candidate and reports for all required rollout hosts using the existing release-evidence schema. The staged artifact report is exploratory and carries `admission: false`. Fleet Sync acts on approved registry entries.

## Earlier routed artifact pilots

Status: experimental, supervised native-Windows lane. This extends `tools/eval.py`; it is not a replacement evaluator, admission gate, sandbox, or production scheduler.

This runner injects instructions and disables child delegation and normal host discovery. It cannot test a full architecture workflow or naturally loaded baseline. Before any model spend, match the intended claim to the task and execution surface. Passing runtime checks does not validate an experiment's design.

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


## Consolidated runtime controls, 2026-10-20

The completed reviewed-host runtime interfaces are integrated into the experimental lane: bounded native deadline/interrupt cleanup, disposable no-install LSP configuration, an explicit direct Python argv terminal, preserved workflow accounting, opt-in private request recording and source-bound continuation validation. Request archives require a separately approved private parent; they are never public source or evidence of execution authentication. Old plans remain unchanged and do not gain new capabilities retrospectively.

The optional native tool-study controller and adaptive dispatcher remain outside this source candidate. Their synthetic mechanism checks do not establish native actor/model exposure or skill usefulness, and the adaptive model gate remains closed. Existing privacy, action admission, native tool guards, oracle acceptance and no-fallback boundaries remain prerequisites.
