---
name: github-issues
description: Create, search, triage, edit, comment on, transfer, close, or reopen a GitHub issue with duplicate checks, repository ownership validation, source-backed evidence, maintainer-grade writing, and live readback. Use github-follow-up for recurring or multi-thread sweeps; use github-pr-workflow when implementation and a PR are also required.
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [github, issues, triage, bug-report, feature-request]
    related_skills: [github-auth, github-pr-workflow, github-follow-up, systematic-debugging]
---

# GitHub Issues

Use `gh` by default. An issue is a maintainer work item, not a transcript of the agent’s process. Gather enough evidence to route, reproduce, or falsify the report; then publish the smallest accurate artifact.

## 1. Establish repository and auth

Use the user-provided URL/repo first. Otherwise inspect the live git remote and runtime ownership:

```bash
gh auth status
gh repo view OWNER/REPO --json nameWithOwner,url,hasIssuesEnabled,viewerPermission
git remote -v
```

Products can move between standalone and monorepo repositories. Verify which repo owns the active runtime/source before creating, transferring, closing, or recreating an issue. If an existing issue is maintainer-triaged in a plausible repo, do not close it merely because another repo also looks likely; add ownership evidence and let maintainers transfer when appropriate.

Read current issue templates and contribution guidance. Use `github-auth` for Windows/WSL auth surfaces rather than extracting tokens.

## 2. Classify and gather evidence

Classify as:

- **Bug:** behavior violates expected/documented behavior.
- **Feature/extension gap:** desired behavior lacks a supported path.
- **UX improvement:** technically functional behavior creates concrete avoidable friction.
- **Triage/management:** metadata, assignment, status, or discussion operation on an existing issue.

For uncertain failures, use `systematic-debugging` before publishing. Gather what is relevant:

- minimal reproduction and frequency;
- expected vs actual behavior;
- version, OS/frontend/runtime, and config surface;
- exact errors/logs/screenshots without secrets or private data;
- source files/functions or state/process evidence when it helps route the issue;
- impact and workaround;
- confirmed facts separated from suspected cause.

Preserve the user’s exact complaint dimension. Do not turn a specific stale label, spacing defect, or lifecycle mismatch into a generic performance/UX issue.

Check existing settings, documented workarounds, and controllable local causes that could falsify the report. Do not file an upstream bug when evidence supports only local misconfiguration.

## 3. Search for duplicates and overlap

Search open and closed issues with several terms drawn from symptom, component, error text, source path, and expected behavior:

```bash
gh issue list --repo OWNER/REPO --state all --search "<terms>" --limit 50
gh search issues --repo OWNER/REPO "<terms>" --state open
gh search issues --repo OWNER/REPO "<terms>" --state closed
```

A single search is insufficient. If body search/quoting is unreliable, fetch issue data and scan titles/bodies locally:

```bash
gh api --method GET repos/OWNER/REPO/issues -F state=all -F per_page=100 -F page=1
```

Do not use `-F` without `--method GET` for reads; it can accidentally issue POST.

Treat a hit as duplicate only when it describes the same user-visible failure and expected fix. For a close match:

- comment with genuinely new evidence;
- cross-link a distinct narrow issue and state the boundary;
- avoid creating a parallel issue merely to improve wording.

When moving repositories, audit the destination before transfer/recreation. Prefer transfer when permissions allow; otherwise cross-link and preserve history.

## 4. Write the issue

Use only sections that add evidence:

```markdown
## Summary
<one precise sentence>

## Environment
- Version/platform/runtime

## Steps to reproduce
1. ...

## Actual behavior
...

## Expected behavior
...

## Evidence
<logs, screenshot, source/state findings>

## Impact
...

## Suspected area
<label as hypothesis; omit if weak>

## Workaround
...
```

For feature/extension requests, replace reproduction with motivation, current limitation, acceptance criteria/proposed surface, and alternatives tried.

Write for maintainers:

- `humanizer` is the sole owner of prose and information order; this skill owns evidence, issue scope, required fields, and publication. Draft in the final voice from the first sentence rather than adding a local style checklist or post-hoc cleanup pass.
- concise component-scoped title;
- no “I searched issues” narration, apology, or agent process history;
- no credentials, private transcript text, or raw local personal data;
- one maintainable change per issue;
- repository-specific template/tone;
- source notes only when they sharpen routing.

Use a Markdown body file for multiline text and Windows paths.

## 5. Publish and verify

```bash
gh issue create --repo OWNER/REPO --title "<title>" --body-file issue.md
gh issue view N --repo OWNER/REPO --json number,url,title,body,state,labels,assignees,author,comments
```

Read back title, body, state, labels, assignees, and visible comments. Label/assignment writes can fail independently from issue creation; report verified state and permission errors without posting cleanup comments to the issue.

If a body/comment publishes with quoting or encoding damage, edit it promptly and read it back again.

## 6. Existing issue operations

Before mutation, fetch current state and relevant comments. Apply the smallest useful change:

```bash
gh issue edit N --add-label "bug"
gh issue edit N --add-assignee @me
gh issue comment N --body-file comment.md
gh issue close N --reason completed
gh issue reopen N
```

Do not delete/recreate merely for style. Recreate only when the existing artifact is materially misleading, unrecoverable, spammy, or cannot be edited/transferred. Preserve maintainer discussion/history whenever possible.

For bulk operations, list/review exact targets first. Do not pipe broad searches directly into destructive close/edit loops without a dry inventory.

## 7. Learn from corrections

When the user corrects how an issue was researched, scoped, filed, or repaired, update this skill or its owning reference rather than storing the correction as user memory. Use memory only when the correction expresses a genuinely user-specific preference; reusable agent behavior and workflow rules belong in the task skill.

## 8. Specialized reference routing

Load detailed references only when the case matches:

- `references/maintainer-grade-issue-audit.md` — deeper quality audit.
- `references/repo-ownership-and-issue-migration-pitfalls.md` — ambiguous ownership/transfer.
- `references/audit-recreate-issue.md` — whether to repair vs recreate.
- `references/product-ux-umbrella-issue-pattern.md` — shared product-principle umbrella vs separate defects.
- `references/source-backed-desktop-ux-issue-pass.md` — several speculative Desktop reports requiring source inspection/splitting.
- `references/update-issue-overlap-and-controllable-causes.md` — update/progress overlap.
- `references/desktop-session-bleed-issue-pattern.md` and `references/desktop-status-and-screenshot-scope.md` — Desktop session/status screenshot scope.
- `references/hermes-desktop-repo-routing.md` — historical integrated-vs-standalone Desktop ownership evidence; revalidate current runtime.

Dated examples are evidence patterns, not automatically current facts.

## Pitfalls

- Issue creation is not complete until live state is read back.
- A screenshot can support several hypotheses; preserve the stated complaint.
- Do not promise a PR when the user asked only for reporting.
- When the user asked for both issue and PR, continue with `github-pr-workflow` after the issue step.
- Public threads should contain product evidence and decisions, not agent hygiene narration.
