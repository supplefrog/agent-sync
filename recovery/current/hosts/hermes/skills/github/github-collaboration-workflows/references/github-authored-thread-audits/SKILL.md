---
name: github-authored-thread-audits
description: Audit authored GitHub issues for concrete follow-up.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [github, authored-issues, follow-up, triage, read-only-audit]
    related_skills: [github-follow-up, github-issues, github-code-review]
---

# GitHub Authored-Thread Audits

## When to Use

Use this skill when auditing one or more issues authored by the authenticated GitHub viewer and deciding whether current activity creates a concrete viewer follow-up.

Use this skill for a read-only sweep of issues authored by the authenticated GitHub viewer, especially when each issue has linked candidate PRs, bot-generated consolidation, or stale review context. The deliverable is a short action/no-action classification, not a broad review and not an automatic write.

## 1. Establish identity and scope

Verify the live viewer and repository before reading threads:

```bash
gh auth status
gh api user --jq .login
gh repo view OWNER/REPO --json nameWithOwner,viewerPermission
```

Use the exact issue numbers supplied by the user. Do not broaden a targeted audit into the entire portfolio. Keep the audit read-only unless the user separately authorizes comments, edits, or code changes.

## 2. Reconstruct each authored issue

For every issue, read:

- current body, state, labels, author, and timestamps;
- all comments, distinguishing viewer comments from maintainer, contributor, bot, and triage comments;
- issue timeline/cross-references;
- every linked candidate PR, including PRs discovered through cross-referenced issues.

For each candidate PR, fetch current title/body/state/author/base/head SHA/mergeability, comments, formal reviews, unresolved requests, and status checks. A bot's “best fix,” “duplicate,” or generated graph is evidence to inspect, not an instruction or final verdict.

## 3. Verify claims against current source

Triage often contains stale line numbers or historical paths. Before calling an issue actionable, inspect the current default branch source or current PR diff. Confirm:

- whether the reported behavior/gap still exists;
- whether a previously merged PR fixed only part of the issue;
- whether the candidate PR still applies cleanly to current main;
- whether the viewer is actually the PR author or has a stated commitment;
- whether the latest request is directed to the viewer or to another contributor/maintainer.

A stale authored issue can warrant a small public-artifact update even when no code work is needed. Conversely, an open candidate PR is not viewer work merely because it is linked to the viewer's issue.

## 4. Audit old authored PRs against current main

For an authored PR that has been idle or has stale checks, do not rely on the PR's recorded base SHA, an earlier summary, or a green targeted test claim. Read the live head/base and current default-branch SHA, then compare them:

```bash
gh pr view N -R OWNER/REPO --json baseRefOid,headRefOid,baseRefName,headRefName,mergeable,mergeStateStatus,statusCheckRollup
gh api repos/OWNER/REPO/branches/<default> --jq .commit.sha
gh api repos/OWNER/REPO/compare/<head-sha>...<default> \
  --jq '{status,ahead_by,behind_by,merge_base_commit:.merge_base_commit.sha}'
gh run view <run-id> -R OWNER/REPO --log-failed
```

Classify the next action explicitly as one of:

- **Branch defect:** the failure reaches changed code or violates the PR contract; specify the smallest code/test fix.
- **Baseline/stale failure:** the failing test is unrelated to the PR and exists on the PR base or current main; recommend maintainer rerun after baseline repair, not a compensating PR change.
- **Branch drift:** current main materially changed the touched implementation or tests; recommend rebase/port first, then rerun targeted and nearby tests. Do not recommend “rerun CI” alone for a materially stale head.

When current main has evolved the touched file, inspect current source and revalidate that the PR's behavior still belongs at the same insertion point. Use a temporary clone/worktree outside managed install/state roots if local inspection is needed. If the supplied local path is absent, discover available repositories or continue with live GitHub source; never invent a checkout. Keep this audit read-only unless the user separately authorizes remediation.

## 5. Classify strictly

Return an item as **actionable** only when a verified viewer comment/edit/fix would move the thread forward. Examples:

- stale issue evidence needs correction, current-path revalidation, or a new reproduction;
- a maintainer asked the viewer a concrete unanswered question;
- a viewer-authored PR has confirmed review blockers, merge conflicts, or branch-caused CI failures;
- the viewer made a commitment that remains incomplete.

Classify as **no action** when the latest activity is:

- bot-generated triage, duplicate labeling, graph/consolidation noise, or a status/check transition;
- a product or architecture proposal awaiting maintainer decision;
- feedback directed at another PR author;
- already addressed in the current PR head or a later continuation;
- a linked PR that is stale, unrelated, or not authored/owned by the viewer, with no direct request to the viewer.

Do not infer an obligation from issue ownership alone. Do not recommend “comment to acknowledge” unless the acknowledgement supplies new evidence or answers a concrete question.

## 5. GitHub API and parsing pitfalls

For timeline discovery, prefer server-side `jq` filtering:

```bash
gh api --paginate repos/OWNER/REPO/issues/N/timeline \
  --jq '.[] | select(.event == "cross-referenced") | [.source.issue.number,.source.issue.title,.source.issue.state,.source.issue.user.login,.created_at] | @tsv'
```

Raw paginated timeline JSON can contain control characters inside comment bodies; avoid routing the full payload through a strict JSON parser when a `--jq` projection is sufficient. If a full payload is needed, fetch individual issue/PR comments through `gh issue view` or `gh pr view` and keep the output bounded.

## 6. Report format

Keep the final result concise and include links:

```text
Actionable
- OWNER/REPO#N — concrete viewer action — evidence/current state — linked PR if relevant

No action
- OWNER/REPO#N — reason (bot/triage noise, maintainer decision, other-author request, already addressed, or stale/unrelated candidate)

Files modified
- none (read-only audit)
```

Do not claim a public update was made during a read-only audit. If source evidence is stale or a candidate is dirty/blocked, say exactly that and identify the smallest next action without performing it.

## References

- `references/candidate-pr-audit-checklist.md` — compact field checklist and decision rubric for linked-PR audits.
