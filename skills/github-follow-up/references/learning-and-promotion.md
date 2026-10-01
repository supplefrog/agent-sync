# Conditional learning and promotion

Read this for a workflow-learning classification, a plausible merged replacement, or any proposed persistent lesson from GitHub evidence. Complete live reconstruction in [SKILL.md](../SKILL.md) first; discovery alone does not establish a reusable lesson.

### Merged-replacement learning

Trigger this comparison only when a live authored PR is closed without merge, explicitly superseded, or plausibly loses to a merged implementation for the same observable requirement. A shared issue or nearby timing is discovery evidence, not proof of replacement.

1. Re-read the authored PR and linked issue/timeline. Identify plausible merged PRs or commits from cross-references, explicit supersession, and matching behavior/mechanism. Exclude same-issue changes that solve a different requirement.
2. Fetch both diffs, review discussions, checks, the winning merge commit, and current base. Verify that current base contains the claimed winning behavior.
3. Compare root-cause coverage, scope, compatibility, tests, maintainability, architecture fit, review corrections, and timing. Separate observed evidence from inference; merge choice or maintainer preference alone does not establish technical superiority.
4. Retain a lesson only when evidence supports a narrow reusable rule or check that would change a future decision. Inspect the owning GitHub/coding rules and evals first: if they already encode the lesson, record confirmation only and make no persistent edit; otherwise adapt or remove an existing rule before adding prose, then apply the cross-project promotion gate below. Never retain PR numbers, commit SHAs, project trivia, task outcomes, or one maintainer's taste.
5. Make no workflow change when our implementation is equivalent or better, the advantage is uncertain or project-specific, or only preference distinguishes the winner. If our PR is later merged, reopened, or force-pushed, classify its current live state instead of treating the earlier terminal snapshot as a loss.

Replacement analysis is read-only unless the live thread independently requires an authorized issue/PR action. Do not post, close, merge, or resolve anything merely to record a lesson.

### Cross-project promotion gate

For any GitHub-derived lesson meant to improve coding, testing, debugging, architecture, or review outside the source repository:

0. On an actual follow-up, complete the live reconstruction in Sections 1–2: inspect the source issue/PR, relevant diffs, reviews, checks, replacement lineage and merge commit when applicable, and current base. In a hypothetical or evaluation prompt that explicitly stipulates evidence but provides no real identifiers, reason from the stipulated facts, label them as not live-verified, and make no external or persistent change on that basis alone.
1. Treat the lesson as a candidate, not a rule. The GitHub automatic-patch path must not mutate the general owner.
   - On an actual follow-up, use skill discovery to inspect the narrowest existing owner and state whether it already encodes the lesson.
   - In a hypothetical or evaluation prompt that explicitly stipulates owner contents, use that stipulated state instead of substituting an unrelated local installation.
   - If a hypothetical does not stipulate owner contents but the owner is accessible, inspect it. Only when no owner is accessible may you name the narrowest plausible existing owner and keep the conclusion conditional.
   - If the inspected or stipulated owner already encodes the lesson, record confirmation and make no persistent edit.
2. Freeze the current owner as the baseline. Using that owner's admission protocol, select fresh held-out coding cases from repositories unrelated to the source evidence and predeclare the outcomes before running the candidate. Include correctness and root-cause coverage when applicable, plus relevant compatibility, verification, maintainability, latency, or cost bounds. PR acceptance rate is not a quality metric.
3. Run deterministic checks and a matched baseline-versus-candidate evaluation. If the owner has no usable admission protocol, the cases are unavailable, or the evaluation is inconclusive, do not promote.
4. Promote only when the candidate improves the predeclared outcomes without a material regression. On a tie or loss, make no persistent rule edit; retain only public-safe negative evaluation evidence when useful. Keep project-specific conventions local.
5. Report **Source verification**, **Ownership check**, **Owner**, **Baseline**, **Held-out cases**, **Predeclared outcomes**, **Deterministic checks**, **Result**, and **Decision: promote/no edit** so the gate is auditable.

GitHub-workflow-only corrections stay in this skill and use direct workflow tests; do not force unrelated coding cases onto a GitHub-specific procedure. Resolve the canonical or live owning artifact through skill discovery/source ownership before claiming it is inaccessible—an empty task workspace is not enough. A prewritten fixture file is unnecessary when the scenario provides enough structure to reconstruct a safe synthetic regression; build it in temporary space and remove it afterward. When the reproducer and owner are accessible, execute the regression, nearby checks, and read-back verification in the current run before retaining or reporting the correction; do not merely propose later testing. If they remain inaccessible, report the concrete blocker in **Waiting** instead of claiming verification.

### Workflow or Hermes-surface improvements

Use `hermes-self-engineering` and `instruction-authoring`.

A manual or scheduled run may automatically patch only this GitHub skill, its reference/script, or its narrow Hermes integration. Require a deterministic reproducer; stage the smallest diff; show the baseline failure and post-change pass plus relevant near-miss checks; inspect the diff; load/read back the promoted artifact; and record rollback. If any condition is missing or the change exceeds that allowlist, put it in **Waiting** for user review. A general engineering candidate must instead pass the cross-project promotion gate and the owning capability's admission checks; it is never an automatic follow-up patch.

Do not automatically change models/providers, credentials, global prompts/SOUL, package sets, services, broad config, plugins, or installed source. Do not turn one maintainer preference into a global rule. Put these in **Waiting** with the evidence and smallest proposed change for user review.

