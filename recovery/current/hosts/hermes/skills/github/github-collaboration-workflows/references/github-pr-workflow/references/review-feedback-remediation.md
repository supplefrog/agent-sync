# Remediating review feedback on an existing upstream PR

Use this when a maintainer or automated reviewer finds problems after a source-change PR is already open.

## Reconstruct the complete review state

Read all of these before editing:

- live PR head/base SHAs, body, merge state, and checks;
- formal review bodies (important findings may have no inline thread);
- top-level PR comments;
- inline comments and review-thread resolution state;
- linked issue requirements.

Do not treat the visible inline thread list as the whole review.

## Refresh before fixing

Fetch the current base and measure ahead/behind. If the PR is stale, rebase or otherwise update it before coding, then verify the original premise still holds on current base. Use a clean dedicated clone/worktree rather than editing an installed application tree.

## Convert comments into behavior contracts

For each finding, state the externally observable contract and inspect sibling paths.

For async initialization/backlogs:

- define a hard count or byte bound;
- define overflow behavior and observability;
- buffer every eligible sibling lifecycle operation, not only the reported hook;
- serialize the readiness check and enqueue/flush transition with the same lock so an operation cannot arrive after the flush snapshot;
- decide what happens after initialization fails. If retry state is retained, later eligible events should either retry or the narrowed durability guarantee must be explicit;
- distinguish pre-existing shutdown/order limitations from regressions introduced by the patch.

For teardown/resource registries:

- cover the registered prototype and every live clone/child that owns independent resources;
- mark the registry closed under the same lock used for membership before taking the shutdown snapshot;
- ensure additions that race after that boundary are immediately closed and rejected rather than joining an already-drained registry;
- prefer weak membership when the registry must not retain otherwise-dead runtimes;
- test a normal pre-shutdown clone and a late post-boundary clone, and verify real handles can be deleted/reopened after cleanup.

Fix the bug class, but do not absorb unrelated pre-existing architecture merely because an independent reviewer noticed it.

## Test the contract, not the container

For bounded async queues, the regression test should:

1. hold initialization in flight;
2. enqueue enough mixed eligible operations to overflow the bound;
3. assert no remote side effect occurs while initialization is blocked;
4. release initialization;
5. assert retained operations execute and dropped operations do not;
6. cover retry after an initialization failure when retry is part of the intended contract.

An assertion on an internal deque/list alone is insufficient: it proves representation, not behavior.

## Independent review loop

After targeted and nearby subsystem tests pass, obtain a fresh-context review focused on real call paths, concurrency, retries, partial failure, and whether tests prove the requested behavior. Evaluate findings rather than applying them blindly. If a blocker is fixed, rerun the reviewer against the updated production diff and verify which commit the review actually covered; a later test-only commit must not be mistaken for an unreviewed production change. Inspect new inline comments as well as the formal review body before declaring the loop clean.

## Publish and close the loop

- Fetch the current base again immediately before the final push or sync claim. If the PR base advanced during remediation, rebase once more and rerun the targeted verification on the final commit.
- Amend or commit narrowly and push with `--force-with-lease` only when history was intentionally rebased/amended.
- Update stale PR-body claims and exact test results.
- Reply to each inline finding with the implementing commit and behavior change.
- Add one concise top-level summary when review-body findings were not represented by inline threads.
- Resolve only threads actually addressed.
- If a final rebase changes a commit SHA already named in public replies or comments, edit those artifacts after pushing; do not leave links pointing at superseded history.
- Read back the live PR base/head SHAs, body, comments, thread state, mergeability, and checks; verify the local base tracking ref, local head, remote branch, and PR head all match the claims.
