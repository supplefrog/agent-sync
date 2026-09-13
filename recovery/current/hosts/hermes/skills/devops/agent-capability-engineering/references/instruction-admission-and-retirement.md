# Instruction admission and retirement

Use this gate before adding, broadening, merging, porting, or deleting persistent instructions, skills, agent definitions, or cross-host behavior surfaces. Model behavior is nondeterministic: textual overlap and one successful run are not promotion evidence.

## Ownership boundary

- Recover prior attempts and current native owners before creating another evaluator or instruction package.
- Validate the evaluation harness before allowing it to gate broader surface changes.
- Treat instruction evaluation as capability admission/retirement governance. Use `skill-creator` for skill-specific suite mechanics when useful; this reference owns the promotion decision.

## Evaluation contract

1. Define the observable outcome, required hosts, hard failures, non-goals, rollback, and cost bound.
2. Compare the live baseline with one coherent candidate. Do not combine every instruction set into a larger candidate merely to preserve overlap.
3. Normalize controllable model, provider, reasoning, prompt assembly, tools, context/truncation, and decoding settings. Record irreducible differences.
4. Use representative positive cases, near-miss/non-trigger cases, adversarial cases, and held-out regression cases. Deterministic checks enforce critical requirements before subjective judging.
5. Calibrate the harness with A/A, known-effect, and transport controls before it can gate mutations. Then run matched baseline/candidate trials on stable case IDs with anonymous randomized labels and order-swapped judging; preserve case, repeated-generation, judge/order, and host-stack variance separately.
6. Predeclare practical improvement, regression, and non-inferiority margins; protected-case rules; alpha/confidence method; minimum evidence; maximum trials; and maximum agent-run budget. Use a bounded anytime-valid or predeclared group-sequential rule. One trial, one judge order, and post-hoc repetition are not evidence; noisy boundary results are `inconclusive`.
7. Admission requires material improvement with no critical failure or required-host regression. Retirement requires non-inferiority on required outcomes. Share one winner across equivalent effective stacks; retain a native variant only for a material reproducible host interaction.
8. Aggregate required-host reports only when candidate, baseline, suite, harness, and declared effective-stack equivalence match; record irreducible host differences. Missing hosts, mismatched fingerprints, timeout, interruption, delivery failure, or judge failure are inconclusive.
9. Select one coherent winner and remove, archive, or disable inferior/conflicting duplicates only after provenance, rollback, and fresh-host verification. Preserve irreducible native strengths as routing signals rather than flattening them.
10. Hash-bind candidate, baseline, suite, harness, routes, models/providers, reasoning, prompt/tool/context policy, seeds, trials, decision rule, and rollback in the report. Re-run in fresh equivalent sessions after promotion.

## Harness and child-session lifecycle

- Give evaluation children an explicit source tag and isolate their workdirs/config so baseline and candidate do not contaminate each other.
- Capture outputs, errors, routes, hashes, and judgments durably before cleanup.
- After the child process is confirmed ended and the report is readable, delete only agent-created evaluation sessions through supported session lifecycle controls. Cover success, rejected candidate, timeout, interruption, and judge failure. Provide an explicit evidence-retention override for debugging.
- Never delete the user/parent session, active/shared/referenced sessions, or sessions whose unique evidence has not been integrated. Verify cleanup by readback.
- A harness/delivery/judge failure is an evaluation failure, not evidence that the baseline or candidate is worse.

## Re-evaluation triggers

Re-run the cheapest representative suite after a materially stronger model, changed prompt/tool protocol, changed host precedence, evaluator change, or evidence that an instruction has become redundant. Retire instructions only through the same no-regression gate used for admission.
