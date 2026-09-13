# Statistically Controlled Instruction and Workflow Evaluation

Use when stochastic behavior could make an instruction, skill, workflow, or host adapter appear better or worse by chance. This reference owns effect attribution; transport and promotion remain owned by their existing references.

## 1. Define the comparison stratum

Fingerprint the effective inference stack: provider/transport, model snapshot, reasoning/decoding, prompt assembly and placement, context/truncation, tool policy/schema, runtime/host adapter, suite/split, harness, deterministic graders, semantic judge/rubric, and decision margins.

- Equivalent fingerprints: reuse one behavioral result and run deterministic discovery/transport parity checks.
- Differing fingerprints: probe only the differing mechanism.
- Suspected host effect: estimate candidate×host interaction; create a native variant only when that interaction is materially different and reproducible.

## 2. Calibrate the harness before candidates

- **A/A negative control:** compare identical baselines under anonymous labels and randomized order. Measure false-positive, judge-disagreement, and position-flip rates.
- **Known-effect positive control:** compare against a deliberately degraded or invariant-breaking variant. Require the harness to detect it.
- **Transport canary:** prove both arms read the full isolated envelope and received equivalent tools/configuration.
- Harness, delivery, or judge failures are infrastructure failures, never candidate losses.

## 3. Use matched evidence

Run baseline and candidate on the same stable case IDs. Randomize execution and presentation order. Prefer deterministic outcome/state checks; for semantic judgments, judge anonymous A/B and B/A presentations and mark inconsistent pairs unstable.

Store raw long-form observations, not only verdicts: case/split, stack fingerprint, treatment, run/seed or nonce, grader/judge, presentation order, scores, artifacts, latency, tokens/cost, and failure class.

## 4. Separate effect from variance

Estimate paired treatment differences and separate case difficulty, within-case generation noise, judge/order noise, host variance, and candidate×host interaction.

- Complete modest samples: two-level nested bootstrap, resampling cases then runs within case.
- Binary paired outcomes: McNemar or another calibrated paired binary procedure.
- Incomplete/factorial data: mixed-effects analysis may diagnose variance, but an experimental model implementation must not be the sole gate.
- Use a randomly sampled human-labeled subset when calibrating a noisy LLM judge; convenience-labeling only borderline cases biases correction.

## 5. Predeclare practical boundaries

Set before seeing results:

- minimum useful improvement;
- maximum tolerable aggregate regression;
- protected critical-case rule;
- maximum host interaction compatible with one common winner;
- maximum budget and uncertainty method.

Classify `admit`, `reject`, `practically_equivalent`, or `inconclusive`. For removable generic steering, demonstrated equivalence favors deletion. Noise is inconclusive, not permanent retention or a win.

## 6. Allocate evidence and stop without peeking bias

Do not choose an arbitrary repetition count and vote, and do not pool repeated outputs as independent task cases. Start with a small matched pilot and estimate between-case treatment heterogeneity separately from within-case generation variance. Add new task cases when case heterogeneity dominates; add repetitions only while run noise remains material. Equal seeds may block some noise when supported, but different prompt/token paths are not guaranteed to share randomness.

Use an anytime-valid confidence sequence for bounded paired differences or predeclared group-sequential looks with alpha spending. Begin with broad uniform case coverage; allocate later budget to underrepresented strata according to the pilot variance components. Adaptive selection can become biased or inefficient when historical difficulty predictions are wrong, so preserve a uniform exploration floor and treat ordinary fixed-time confidence intervals as invalid for repeated peeking.

## 7. Research and improvement loop

Use one shared lifecycle, scaled to the change:

1. Define outcome and protected invariants.
2. Inventory native owners, existing skills/frameworks, and established methods.
3. Retain or adapt an adequate solution; research papers only for unresolved mechanisms; use new-architecture research only after prior art fails.
4. Develop on representative/near-miss/adversarial cases; preserve held-out and regression cases for selection control.
5. Run the calibrated paired gate.
6. Promote one reversible winner; feed verified production failures back into the suite.

Do not rerun broad research for exact duplicates, deterministic wiring, or unchanged evidence cells.

## 8. Model-release evidence cache

Persist append-only raw observations keyed by the effective-stack and evaluation identities above. Compute verdicts as views so a better statistical method can reanalyze old generations.

A release/catalog signal starts route research only. Open instruction retirement when a callable stack is selected or recommended for an active route; statically filter unchanged task procedures and protected guarantees, then evaluate only invalidated model-sensitive cells. Detection and evidence generation may be automatic; live route or instruction mutation remains separate and reversible.

## Research basis

- `evalstats`: paired comparisons, nested bootstrap, run/input variance decomposition, judge-bias correction.
- Inspect AI: stable sample IDs, epochs, structured logs, resumable eval sets.
- Dror et al. (ACL 2018): test selection and statistical significance in NLP.
- Howard et al. (Annals of Statistics 2021): anytime-valid confidence sequences.
- LLM-evaluation work on benchmark uncertainty, multiple generations, multi-prompt robustness, and judge position bias.

Adapt these mechanisms into the current harness before replacing it or adding a new evaluation authority.
