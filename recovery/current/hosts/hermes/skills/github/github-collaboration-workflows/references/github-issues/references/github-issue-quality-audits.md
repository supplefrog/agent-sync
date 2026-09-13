---
name: github-issue-quality-audits
description: "Audit existing GitHub issues for quality/actionability before editing, closing, deleting, or recreating them."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [github, issues, triage, audit]
    related_skills: [github-issues, hermes-agent]
---

# GitHub Issue Quality Audits

Use this when the user asks to audit an issue, judge whether an agent-created issue is good enough, or delete/recreate/edit an issue if it was poorly written.

## Workflow

1. **Fetch the full issue state first**
   - Prefer `gh issue view <N> --repo OWNER/REPO --json number,title,state,stateReason,author,createdAt,updatedAt,body,labels,assignees,comments,url --comments`.
   - If `gh` is unavailable, use the GitHub REST API endpoints for issue, comments, events, labels, and search.
   - Do not assume the body/title from the URL preview is complete.

2. **Audit before mutating**
   Check whether the issue has:
   - concise but specific title;
   - environment and affected component;
   - observed behavior and expected behavior;
   - exact errors/log snippets where relevant;
   - known workaround or repair path if discovered;
   - clear implementation/diagnostic asks rather than vague frustration.

3. **Check for duplicates and related issues**
   - Search several targeted queries using the repo plus distinctive error terms, component names, and environment.
   - Treat related platform-specific issues as related, not duplicates, unless the root cause and requested fix are materially the same.

4. **Ground the audit in repo reality when possible**
   - Inspect the relevant source paths or docs if locally available.
   - Confirm that the reported failure path is plausible and that suggested fixes point at actual code surfaces.
   - Distinguish confirmed source observations from plausible but unverified claims.

5. **Choose the smallest appropriate action**
   - Keep the issue if it is actionable, even if it could be polished.
   - Edit in place when title/body needs cleanup but the report is basically valid.
   - Label/comment instead of recreating when metadata is the only gap.
   - Close as duplicate/invalid only with explicit evidence.
   - Delete/recreate only when the existing issue is materially misleading, low-signal, or unrecoverable by edit/comment.

6. **Mutate only with verified auth**
   - Before promising label/edit/close/create success, verify a usable GitHub auth path (`gh auth status` or REST token check).
   - If unauthenticated, report the exact recommended command instead of implying the change was applied.

## Labeling guidance

For Hermes Agent issues, prefer the repo's existing label taxonomy:
- `type/bug`, `type/feature`, `type/docs`, etc.
- `comp/cli`, `comp/tui`, `comp/tools`, etc.
- platform/tool/provider labels only when directly applicable.
- priority labels based on impact and workaround availability (`P2` for degraded with workaround; `P1` for major broken/no workaround).

## Pitfalls

- Do not recreate an issue just because an LLM wrote it. If it has the facts and asks for the right behavior, keep it.
- Do not treat missing local tools (`gh` not installed) as a reason to skip audit; use REST read-only calls.
- Do not persist environment-specific failures as broad rules. Capture durable workflow patterns only.

## References

- `github-issue-quality-audits/hermes-install-update-issue-38311.md` — example audit of a Hermes install/update issue involving stale venv and Node native build prerequisites.
