---
name: github-collaboration-workflows
description: Use when working with GitHub repositories, issues, pull requests, reviews, CI, releases, or repository settings. Route authentication to github-auth and repeated portfolio follow-up to github-follow-up.
version: 1.0.2
metadata:
  hermes:
    tags: [github, issues, pull-requests, code-review, repositories, triage]
---

# GitHub Collaboration Workflows

Use this class-level umbrella for GitHub collaboration from repository setup through issue work, PR delivery, independent review, and follow-up. Start by identifying the requested artifact and whether the work is read-only or authorized to mutate GitHub.

## Routing

Load only the branch needed for the task:

- Authentication, account selection, HTTPS tokens, SSH keys, `gh` login, or Windows/WSL `gh`: use the separate `github-auth` skill.
- Issue creation, search, triage, edits, comments, transfers, and closure: `references/github-issues/SKILL.md`.
- End-to-end issue implementation through a verified PR: `references/github-issue-to-pr/SKILL.md`.
- Publishing, updating, remediating, or merging one PR: `references/github-pr-workflow/SKILL.md`.
- Independent review of another person's PR: `references/github-code-review/SKILL.md`.
- Read-only audits of issues authored by the current viewer and linked candidate PRs: `references/github-authored-thread-audits/SKILL.md`.
- Repository creation, cloning, forks, settings, releases, Actions, and secrets: `references/github-repo-management/SKILL.md`.

## Shared invariants

1. Establish live identity, repository, permissions, base/head, and current artifact state before acting. Before conflict remediation, map remote URLs to the PR's actual base repository; fetch its target branch and compare `git rev-parse <base-remote>/<base-branch>` with `gh api repos/OWNER/REPO/branches/BRANCH --jq .commit.sha`. Record the verified base and PR-head SHAs before dispatching work; a cached ref or fork's `main` is not proof of upstream freshness. If the base advances afterward, report the tested snapshot rather than restarting indefinitely.
2. Read full issue/PR discussion and repository guidance; titles and bodies alone can be stale.
3. Search for duplicates and competing work before creating a public artifact; classify each candidate’s viability relative to repository velocity before choosing collaboration, a comment-only delta, or a fresh current-main PR.
4. Separate verified facts from hypotheses, and branch-caused failures from baseline, stale, flaky, or infrastructure failures. Before dismissing a failing verification gate as baseline, reproduce it on the candidate's exact base with the same runner and environment; compare the failing test and stack, not just failure counts. Report the candidate's failures even when the comparison establishes they were not introduced.
5. Use focused branches/worktrees and preserve unrelated user changes. Before upstreaming a plugin incompatibility, distinguish a regression in a supported API from a plugin's dependency on private internals; reproduce against the committed plugin and name the tested host revision. Search both open proposals and closed design decisions, then check current contribution guidance before treating an older rejection as current policy. For a missing SDK capability, contribute concrete consumer requirements to an existing viable proposal rather than opening a duplicate; otherwise propose the generic extension, keeping the feature-specific plugin separate. Explain the blocker as what the plugin expects, what the host provides, and which user action fails before giving symbol names. Keep any authorized temporary adaptation local to the plugin where possible, and do not deploy an enforcement gate until its replacement execution path works. Publication, local adaptation, and deployment are separate outcomes; completing one does not complete the others.
6. Publish multiline bodies from files; never expose credentials or private local data.
7. Read back every GitHub mutation from the exact target before claiming success.
8. Report exact checks, current CI/review state, and bounded untested scope.
9. For iterative automated review, require a clean verdict on the exact current head before stopping; afterward remove bare trigger comments but keep substantive findings, replies, and the final verdict.

## Mode boundaries

- Do not self-approve; use local change verification for your own diff.
- A read-only audit does not authorize comments, edits, pushes, or closure.
- When implementation and a PR are authorized, continue through a tested, read-back PR without another routine consent check. A completed delegated review is an input, not the endpoint: resolve findings, execute remaining verification, then commit, push, publish and verify the PR. If issue linkage is requested, reuse a matching issue or create one after duplicate checks; verify the PR's closing-issue relationship. Treat a later “finish” or cleanup request as continuation of the authorized deliverables, not a silent downgrade to local patches or comments. A related PR that excludes the requested behavior does not replace the implementation. Complete publication before retiring its only recovery copy, and distinguish contribution completion from CI or merge status. Stop only for a concrete blocker or explicit user-directed handoff.
- Opening a PR is not evidence that CI is green, the issue is delivered, or the change is merged.
- For portfolio evidence, classify each selected artifact as original work, adaptation, fork, or upstream contribution; inspect provenance and the relevant diff before attributing authorship. Record PR state and merge evidence separately from local implementation. Inspect each cited test change before calling a collection of contributions test-backed—a verified example does not establish the whole collection.

The detailed branch packages below preserve their templates, checklists, and provider-specific command recipes.