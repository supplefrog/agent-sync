# Learning from merged replacement implementations

Use when an authored PR is closed/unmerged, superseded, or stalls while another PR or commit lands for the same issue or behavior. The outcome is better future work, not a post-hoc claim that every merged patch was technically superior.

## Trigger and evidence

Keep a finite incremental queue of recently terminal authored PRs when a linked issue, closing event, cross-reference, or current-main diff indicates another implementation may have landed. Open-PR-only discovery cannot observe this learning boundary.

Before comparison, verify from live GitHub/current main:

1. the authored attempt did not merge as the effective fix;
2. the replacement actually landed and addresses the same observable behavior;
3. both implementations, tests, review discussion, and relevant current-main context are available;
4. the apparent difference is not only timing, ownership, unrelated scope, or a later base change.

Merge status is evidence of project choice, not proof of technical superiority.

## Comparison

Compare behavior and mechanism, not line shape:

- premise and exact manifestation line;
- root-cause coverage and sibling paths;
- preserved feature intent and compatibility;
- scope and footprint;
- tests as behavioral invariants, including integration/E2E boundaries;
- failure handling, security, concurrency, and lifecycle effects;
- reviewer/maintainer rationale;
- whether the replacement solved a problem the attempt missed or merely arrived through a preferred ownership/timing path.

Reproduce or run available verification when the distinction is material. Separate evidence from inference and state when a “winner” is only organizational rather than technically better.

## Retention gate

Retain a lesson only when it is reusable beyond the specific PR and evidence shows it would have changed the future approach. Update the narrow owning class-level skill/evaluation with the decision rule, pitfall, or test—not PR numbers, commit hashes, repository-specific trivia, or a completed-work log. Prefer replacing stale guidance over appending another exception.

Examples of valid lesson classes: verify the premise on current main before coding; preserve original feature intent; test the real resolution/config/security boundary; compare sibling call paths; avoid source-shape tests; use the repository's shared abstraction rather than a parallel manager.

Do not retain one maintainer’s taste, a non-reproducible review comment, or a result explained only by timing. Record “no reusable lesson” explicitly so the same terminal pair is not repeatedly analyzed.

## Scheduled workflow

A scheduled GitHub gate must include recent authored terminal transitions and keep each candidate pending until the comparison is classified and external readback succeeds. Unchanged ticks remain silent. The expensive diff/review analysis runs only for a candidate replacement pair, not for every closed PR.

The focused GitHub owner performs live discovery and remediation; orchestration owns cross-workflow admission and ensures accepted lessons reach future planning before another related PR is designed.
