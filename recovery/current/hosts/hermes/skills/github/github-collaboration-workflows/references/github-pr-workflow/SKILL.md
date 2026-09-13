---
name: github-pr-workflow
description: Manage one GitHub pull request from a clean branch through duplicate-PR audit, implementation verification, commit, push, PR creation, CI, review remediation, and merge. Also use when a source bug should be upstreamed instead of left as a local patch. Use github-follow-up for recurring or multi-thread sweeps, github-issues for issue-only work, and github-code-review for reviewing someone else’s PR.
version: 2.4.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [github, pull-request, upstream, ci, git]
    related_skills: [github-auth, github-issues, github-code-review, github-follow-up, code-change-verification]
---

# GitHub Pull Request Workflow

Use the official `gh` CLI and git by default. Use `gh api` or REST only for data the high-level CLI cannot expose. Never extract or print credentials from config files.

The deliverable is not a local patch or a claimed push. It is a focused live PR whose issue relationship, head, body, tests, and checks have been read back.

## Modes

- **Publish existing work:** branch, verify, commit, push, create/update PR.
- **Issue + PR:** diagnose, reuse/create the issue, audit active PRs, implement, publish.
- **Upstream local product fix:** prefer supported config/plugin/API first; if source is required, leave the installed/main tree clean and publish from a focused branch/worktree.
- **Remediate review/CI:** reconstruct live feedback/check state, fix, reverify, push, and close the public loop.
- **Merge:** merge only when authorized and repository requirements pass.

## 1. Preflight

Check:

```bash
gh auth status
gh repo view --json nameWithOwner,defaultBranchRef,url,viewerPermission
git status --short --branch
git remote -v
```

Read repository guidance and the current PR template. For repeated Hermes Agent contributions, use `references/hermes-agent-contributing-pr-notes.md` first, then refresh from live `CONTRIBUTING.md` when stale or incomplete.

Do not mix unrelated user changes into the branch. Prefer a dedicated worktree/clone when the installed application tree must remain update-clean. Put that worktree **outside the application's managed state/install root** (`$HERMES_HOME` for Hermes): an updater or stale-artifact cleanup can remove managed subdirectories and destroy uncommitted work. Use a normal project/temp path, then remove it after publishing.

### One-writer ownership

Before any source edit, commit, push, PR mutation, or review reply, establish one active writer for the target repository, branch, and PR. Inspect current worktrees, branch/head state, and explicit handoffs. If another user or agent is actively writing the same branch or PR, remain read-only until there is an explicit handoff; do not race pushes or independently mutate public state. A handoff is not itself a scope reset. While handoff is the current decision, do not project downstream clean-environment, negative-control, or review requirements into that decision; they are not yet applicable. After an explicit handoff, reconstruct the current base, head, requirements, scope, and evidence before deciding which downstream checks are required instead of continuing a stale plan.

## 2. Confirm the source-change path

Before editing source:

- verify the symptom/root cause or requested feature boundary;
- prefer documented config, plugin, CLI, or extension surfaces when they solve the requirement;
- use `systematic-debugging` for uncertain failures;
- use or create a GitHub issue when the repo expects issue linkage or the user asked for one.

For issue creation/search/triage, use `github-issues`. Do not stop after issue creation when the request also includes a PR.

## 3. Audit duplicate and competing PRs immediately before coding

Issue search alone is insufficient. PRs can appear minutes after an issue is filed.

1. Search open and recently closed PRs by issue number, symptom, approach, subsystem, touched path, and branch/title terms.
2. For an existing issue, inspect timeline-linked/cross-referenced PRs and comments containing manual PR links. Keyword searches can miss them.
3. Inspect every plausible match:

```bash
gh pr list --state open --search "<issue-or-approach terms>" --json number,title,url,headRefName,updatedAt
gh search prs --repo OWNER/REPO "<symptom OR code-path terms>" --state open
gh pr view N --json state,title,body,files,commits,statusCheckRollup,maintainerCanModify
gh pr diff N --patch
```

Do not equate “exists” with “viable.” Measure draft/review/check state, substantive author or maintainer activity, merge-base, and ahead/behind counts against current default branch, then compare calendar age with repository movement over the same interval. If a viable current PR covers the same mechanism, test it, review it, contribute an apply-ready delta, or track it. If it is dormant or materially diverged relative to project velocity, prefer a focused current-main PR over a comment that maintainers are unlikely to notice; credit/link the earlier work and state exactly what was reused, changed, or independently verified. Do not use a universal age or commit cutoff.

Learn from competing work before coding: test placement, existing helpers, adjacent semantics, CI signal, and maintainer conventions.

## 4. Create a focused branch and implement

Start from an updated clean base and use a descriptive branch:

```bash
git fetch origin
git switch <default-branch>
git pull --ff-only
git switch -c fix/<issue>-<topic>
```

Implement the smallest complete fix. Preserve adjacent semantics and repository conventions. Avoid unrelated cleanup and new behavioral environment variables where a normal config surface exists.

For bugs, tests should exercise the production seam. Stateful fixes should drive producer → persistence/transition → consumer/reload. Partial, filtered, limited, or paginated reads must not be treated as complete evidence of deletion or absence.

For retryable API writes, require a stable idempotency key to be generated and durably persisted before the first network attempt, then reused across retries and process restarts. Verify the real producer → persistence → API client path, including a failure after the server may have accepted the write; a caller-only mock or a key created after the first attempt does not prove duplicate prevention.

## 5. Pre-public evidence gate

Before the first commit, push, or PR creation, and again after any scope-changing edit, make an explicit **publish**, **hold**, **rescope**, or **handoff** decision from current evidence:

Use these decisions consistently:

- **handoff** when writer ownership conflicts. During the handoff decision, downstream verification and scope-reset fields are not yet applicable; reconstruct them after ownership transfers.
- **rescope** (not hold) when current-base evidence disproves the premise, the user rejects the mechanism, or viable competing work owns it. This is the state that requires a scope reset. If no implementation will be published, clean-environment and fresh-review evidence are not required; the current-base reproducer remains required negative-control evidence.
- **hold** when the requested scope remains valid but any applicable pre-public evidence is missing. Re-running stale verification after an edit is not a scope reset; mark scope reset not required unless the causal claim or implementation boundary must change.
- **publish** only when applicable evidence passes. Tiny non-executable documentation or metadata edits may use the proportional exceptions below.

1. Reconfirm the live requirement, issue state, current base/head, and competing work. If the original premise is disproved or another viable change now owns the mechanism, stop polishing the old solution and rescope. Treat the current-base reproducer that disproves a stale premise as required negative-control evidence for that rescope decision, even when no new implementation is warranted.
2. Run the repository-declared commands in a clean, isolated environment appropriate to the changed boundary. A warmed local state is not evidence for fresh install, migration, startup, reload, or configurable-path behavior.
3. For stateful, concurrent, lifecycle, migration, compatibility, or configuration changes, exercise the effective production boundary and one negative control that would fail under the old or incomplete mechanism.
4. Keep the gate proportional. Tiny documentation-only or metadata-only edits may mark clean-environment, negative-control, and independent-review evidence as not required when no executable behavior changes.
5. Require one fresh read-only review pass for platform-specific behavior, persistence/schema/migration changes, concurrency, security, public API compatibility, or cross-process lifecycle work. The reviewer may be a separate review pass, tool, or agent, but remains read-only; the established writer alone applies fixes. Resolve material objections before publishing or choose **hold**.

Name the concrete seam in the evidence instead of asking generically for more tests. For configurable persisted state, trace the selected-path producer through creation or migration and reopen or reload, and make the old/default path unavailable or distinguishable as the negative control.

Record a compact evidence packet containing the decision, writer ownership, premise/scope check, clean-environment status, negative-control status, fresh-review status, exact verification commands, and residual risk. Free-text confidence cannot override missing required evidence. Do not make the public write unless the decision is **publish**.

## 6. Verify before publishing

Use `code-change-verification` for nontrivial or high-risk diffs.

Minimum evidence:

- original regression/reproduction;
- targeted tests for the changed subsystem;
- nearby tests for shared routing, config, persistence, security, I/O, or lifecycle behavior;
- relevant lint/type checks.

Use the repository’s declared dependency path and correct runner. Do not install ad-hoc packages if the lockfile/project command provides the environment. Let CI own the full matrix on large repositories unless the local full suite is fast and known-clean.

The latest post-edit output is authoritative. If verification becomes stale after another edit/rebase, rerun it. Report exact commands and scope; do not imply a broad suite passed when only a slice did.



## 7. Commit, push, and create/update the PR

Use focused Conventional Commits. Stage explicit files when practical.

```bash
git add <paths>
git commit -m "fix(scope): concise description"
git push -u origin HEAD
```

Prepare the PR body in a Markdown file, especially when it contains Windows paths/backslashes:

```markdown
## Summary
- <what changed and why>

Fixes #<issue>

## Test Plan
- [x] `<exact command>` — <result>

## Notes
- <compatibility, platform, or untested scope>
```

Create or edit with `--body-file`. Follow the repo template honestly; do not check boxes for work not performed.

### Recover a transport-blocked push through the Git Data API

Use this only when an authorized, verified commit cannot be pushed through Git transport but authenticated `gh api` repository writes work. Do not treat a network timeout as an authentication failure or change global credentials to repair it.

1. Freeze the local commit, parent, tree, and changed paths. Read committed blobs with `git cat-file`, not working-tree bytes, because checkout filters or later edits can change their hashes.
2. For an ordinary unsigned commit, POST changed blobs to `repos/OWNER/REPO/git/blobs` with base64 content; verify returned SHAs against the committed blobs. POST a tree to `git/trees` using the parent's tree as `base_tree`, preserving each entry's path, mode, and type. Require its SHA to equal `git rev-parse HEAD^{tree}`. Reject unsupported entry types instead of assuming every file is mode `100644`.
3. POST to `git/commits` with the exact tree, parents, message bytes, author, committer, and timestamps including timezone offsets. Require the returned commit SHA to equal local HEAD before publishing a branch. If signed commits or extra headers prevent exact reproduction, stop rather than silently replacing the tested commit.
4. Create the intended new branch with POST `git/refs`, then GET `git/ref/heads/BRANCH` and verify its SHA. Do not overwrite an existing divergent ref or bypass branch protection. Resume normal PR creation and readback only after that check.
5. Bound retries per object. After an ambiguous timeout, GET the expected blob/tree/commit SHA or branch ref before resending: the server may have completed the write. Resume at the first missing object rather than replaying all uploads. Use `gh api --input` for payloads; never extract a token.

## 8. Read back live state

After every create/edit/push:

```bash
gh pr view --json number,url,title,body,state,headRefName,headRefOid,baseRefName,mergeable,statusCheckRollup
gh pr checks
```

Verify the live title/body, linked issue text, branch/head SHA, check state, and any requested labels/reviewers. Do not claim external writes succeeded from command intent alone.

If scope changes after opening, update every public artifact you control that now makes a stale claim: PR body, issue body, and relevant comments.

## 9. CI and review remediation

For CI failures:

1. inspect failed job logs and annotations;
2. distinguish code regression from flaky/baseline/platform failure;
3. fix the mechanism, rerun local targeted checks, push;
4. re-read the new live checks.

For review feedback, reconstruct formal review bodies, top-level comments, inline comments, unresolved threads, issue requirements, current base, and head before editing. Translate findings into observable behavior contracts and inspect sibling lifecycle paths. See `references/review-feedback-remediation.md` for the detailed sequence.

When the user asks to continue automated review until clean:

1. Confirm the finding and reviewed commit belong to the current head before changing code.
2. Fix the mechanism, rerun only the affected and neighboring verification, push, and read back the remote head.
3. Reply with the concrete commit and evidence, then post one review trigger. Do not stack triggers while a pass is still queued.
4. Stop only when the clean verdict names the exact current head and no newer inline finding exists. A generic review record or reaction is not enough.
5. Treat a transient bot error as incomplete work: confirm no verdict or finding was produced, then retry once.
6. After the clean verdict, delete your own comments whose entire body is only the trigger. Keep substantive findings, technical replies, and the final clean verdict as the useful audit trail.

Reply only when you have a concrete result. Resolve only completed threads. If a rebase changes SHAs cited in your comments, update those public references.

## 10. Merge and cleanup

Merge only when authorized and required checks/reviews pass:

```bash
gh pr merge N --squash --delete-branch
```

Use the repository’s preferred method when known. Read back final PR state.

Restore the user’s normal branch/worktree after upstream work. Remove local install edits unless the user explicitly asked to keep them. Compare installed/main status with the preflight baseline; preserve and report pre-existing user changes rather than trying to make their tree clean.

Before removing a task worktree, verify the remote commit and preserve any required patch/receipt outside it. If `git worktree remove` reports a nonempty directory, inspect both `git worktree list` and the remaining filesystem: deregistration can succeed while dependency files remain. Remove only confirmed task-owned remnants, then verify the path is absent; do not retry removal blindly or touch other worktrees.

## Pitfalls

- Do not create a PR before the immediate active-PR audit.
- Do not narrate duplicate-search process publicly unless it explains the PR’s relationship to another change.
- Do not leave a local source patch as the hidden final deliverable.
- Do not use Bash ANSI-C quoted bodies for Windows paths; control escapes can corrupt published Markdown.
- Do not force-push except for an intentional rebase/amend, and then use `--force-with-lease`.
- Do not merge merely because optional checks are noisy; identify the repository’s actual required state.
