---
name: semantic-merge-verification
description: Use for divergent code merges and semantic verification.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [git, merge-conflicts, code-review, verification, stateful-systems]
    related_skills: [code-change-verification, systematic-debugging, test-driven-development]
---

# Semantic Merge Verification

Use this skill when a reviewed feature must be reconciled with a newer or materially divergent current-main worktree, especially when the conflict touches persistence, lifecycle, concurrency, routing, retries, or cleanup. The goal is a smallest complete merge, not a marker-free file.

## When to Use

Use when a three-way merge, cherry-pick, patch application, or conflict resolution combines a feature with a changed target tree and correctness depends on preserving both production paths. Do not use for a trivial non-overlapping merge whose direct test is obvious.

## Checkout-supersession comparison before cleanup

1. Record the installed HEAD, maintained development HEAD, and candidate local branch tips separately. Inventory dirty, untracked, and ignored source plus linked worktrees; a clean checkout can still own useful unmerged commits.
2. Test `git merge-base --is-ancestor <candidate> <target>` against each exact target HEAD. Treat exit 1 as divergence and other failures as incomplete evidence. Reachability from any ref proves retention only; it does not prove inclusion in the running version.
3. For divergent tips, inspect `git log <candidate> --not <target>` and the corresponding diffs. Compare rebased or cherry-picked changes with `git show --format= <commit> | git patch-id --stable`; different commit IDs can carry identical changes. Check current definitions and callers as well, because equivalent historical patches may have been reverted or replaced.
4. Group equivalent changes before reviewing behavior. Inspect remaining safety or functionality differences and run bounded comparisons against current code, including one negative case. Use temporary state and stop before real update, restart, or deletion boundaries. Exact archived-function execution with controlled dependencies is a narrow probe, not full application verification; report what was stubbed and which production boundary was reached.
5. Classify each change as incorporated, equivalent in maintained development but not deployed, meaningfully different, or unresolved. An old safety policy may be stricter rather than worse. Do not convert recoverability into a supersession verdict or integrate a pending fix under cleanup-only authority.
6. Before authorized removal, preserve unresolved local work and verify recovery. Group linked worktrees by `git rev-parse --path-format=absolute --git-common-dir` and deduplicate branch sets before creating bundles; worktrees share history, so per-worktree bundles duplicate large packs. Verify `git bundle verify` and `git bundle list-heads`; a standalone recovery bundle must have no prerequisite commits. For review, restore into one disposable bare repository instead of importing refs into the live install, then remove that scratch repository after retaining evidence and verified recovery.

## 1. Establish the merge contract

1. Read the repository and worktree instructions before editing.
2. Identify the target worktree, incoming/source worktree, merge base, and the exact files in scope.
3. State the behavior that must survive in one sentence, including important negative guarantees such as “a stale callback cannot affect a successor run” or “never-used rows are prunable but used rows are retained.”
4. Record the target's current-main improvements that must not regress.

Do not modify the source worktree, live configuration, or unrelated repository state.

## 2. Inspect both sides of every conflict

For each conflicted file:

1. Read the working-tree conflict hunk.
2. Inspect the target/current side and incoming/feature side independently (`git show :2:path` and `git show :3:path` during an index conflict).
3. Inspect nearby definitions, callers, schema declarations, migration code, and tests in both trees.
4. Classify each hunk as independent additions, same-behavior edits, incompatible behavior, or a shared invariant that needs a new combined implementation.

Never choose ours/theirs mechanically. Preserve target-only fixes, carry feature behavior through current APIs and schemas, and remove only genuinely superseded code.

## 3. Resolve the real production path

After resolving textual markers, search every newly referenced symbol, column, status, callback, and helper across the target worktree. A clean hunk can still depend on a helper or schema field that was omitted outside the conflict.

Pay special attention to:

- imports and type annotations evaluated at module import time;
- database columns, indexes, migrations, drift rebuilds, and legacy backfills;
- lifecycle status transitions and their callers;
- retries, ownership tokens, run IDs, leases, and stale callbacks;
- cleanup predicates that must protect adopted/shared or still-active state;
- tests that moved between directories or changed fixture conventions.

Adapt incoming code to the target's actual schema and production seam instead of reintroducing removed or stale assumptions.

## 4. Verify in increasing scope

Run checks in this order:

1. compile/import the affected production modules;
2. run the direct regression tests, including the migrated test location;
3. run neighboring lifecycle, persistence, delegation, and concurrency tests;
4. run `git diff --check`, inspect the staged diff, and confirm no conflict markers or accidental source-worktree edits remain.

For stateful changes, test the complete transition: initial state → operation → durable state → cleanup/reload. Include at least one nearby refusal or stale-owner case. For deletion/pruning, test both a complete candidate scan and protected rows with messages, activity, explicit intent, ownership, or routing references.

Do not call a merge complete because syntax checks pass or conflict markers are gone. If targeted tests expose a missing dependency or stale assumption, trace and repair the production path before reporting success.

## 5. Report honestly

Report:

- exact files changed;
- conflict decisions and why they preserve current-main behavior;
- commands and real results;
- test coverage moved or adapted;
- any remaining blocker, without presenting an unverified workaround as a recommendation.

Leave the result uncommitted when the parent agent is expected to review it, unless explicitly asked to commit.

See `references/semantic-merge-checklist.md` for a compact command and review checklist.

## Pitfalls

- Marker-free is not semantically merged.
- A feature hunk may reference a helper, import, or schema column that did not appear in the conflict marker.
- Copying source-branch SQL or fields can break a newer target schema; inspect `CREATE TABLE`, migrations, and rebuild paths together.
- A test added after a merge is not proof if it bypasses the production seam or recreates the algorithm under test.
- Do not report green verification when the targeted suite still has failures; separate completed integration work from remaining blockers.
