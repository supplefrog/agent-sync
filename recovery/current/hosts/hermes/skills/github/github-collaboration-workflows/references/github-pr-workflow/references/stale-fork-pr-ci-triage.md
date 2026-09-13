# Stale fork PR CI triage notes

Use this when an older fork PR is open, a duplicate PR was closed, and maintainers need to decide whether the older PR is actually broken or just stale/noisy.

## Pattern

- Check the live PR checks and conversation first: `gh pr view <N> --json statusCheckRollup,comments,reviews,files,commits,maintainerCanModify,headRefOid,baseRefOid`.
- Read failed logs/annotations: `gh run view <run-id> --log-failed` and `gh api repos/<owner>/<repo>/check-runs/<check-id>/annotations`.
- If a check says it posted a PR comment but no comment exists, inspect annotations. Fork PRs often have read-only `GITHUB_TOKEN`, so comment posting can fail even while annotations explain the blocker.
- Compare the PR's base commit workflow against current `main` when the failure is from CI policy/workflow code. Old fork PRs may run old workflow logic that has since been fixed.
- For security/supply-chain scanners, verify the actual PR diff before treating the check as real. Old two-dot diff logic (`BASE..HEAD`) can include unrelated history; current three-dot diff (`BASE...HEAD`) better isolates PR changes.
- Run targeted tests for the touched subsystem locally or in CI. If targeted tests pass and failures are in unrelated subsystems, report them as unrelated baseline/staleness unless the diff plausibly touches shared behavior.

## Viability is relative to project velocity

Do not classify a PR by calendar age alone. Read its last substantive author/maintainer activity separately from drive-by comments, compare its merge-base and `ahead_by`/`behind_by` counts with current default branch, and inspect how much the repository moved during the same interval. A weeks-old PR can be current in a slow repository and effectively abandoned when hundreds of commits behind a fast one. An `action_required` Actions run on a fork is a maintainer-approval gate, not a passing check or a code failure.

## Duplicate PR handling

When another PR covers the same mechanism:

1. If it is active and reasonably current, do not keep a duplicate open. Test it, review it, and contribute only the unique delta: regression shape, edge case, or apply-ready code suggestion.
2. If it is dormant or materially diverged relative to project velocity, do not rely on a comment-only update. Open a focused current-main PR, credit/link the earlier work, explain why a fresh integration surface is warranted, and distinguish reused ideas from independent fixes.
3. If `maintainerCanModify` is true and the branch is still viable, a maintainer can push a small delta/rebase directly; otherwise ask the author to rebase or use the fresh-PR route above.
4. Update any earlier comment or PR-body claim you control that said no competing PR would be opened; public coordination state must match the new route.
5. Keep the final recommendation short: whether the old PR is safe/viable, which failures are real, and the next concrete action.
