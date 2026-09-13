---
name: persistence-routing-audits
description: "Use when auditing memory/skill routing."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, memory, skills, routing, audit]
    related_skills: [hermes-self-engineering, hermes-agent, hermes-agent-skill-authoring]
---

# Persistence Routing Audits

Use this skill when reviewing whether Hermes is routing a user correction, workflow lesson, or durable fact to the right persistence layer.

## What to inspect

1. **Live source first**
   - Read the current code paths that assemble the prompt or issue the write.
   - Identify the exact paths and line ranges for the foreground prompt, background-review prompt, and any helper that gates memory or skills.

2. **Search for overlap**
   - Look for instructions that belong to a different persistence layer.
   - Pay special attention when memory guidance mentions workflows, procedures, or skills, or when skill guidance is emitted without checking capability.

3. **Check upstream status**
   - Search GitHub issues and PRs for the exact behavior class.
   - Record the exact issue/PR URLs together with the code path evidence.
   - If a fix exists but is still open, report it as an upstream candidate fix, not as a resolved state.

4. **Assess classification risk**
   - Durable facts: user preferences, stable environment details, recurring conventions.
   - Reusable procedures: workflows, debugging sequences, operational fixes, tool usage patterns.
   - Temporary session state: progress, completed tasks, issue numbers, short-lived artifacts.
   - Flag any prompt text that can cause a workflow correction to be written as memory instead of a skill, or vice versa.

## Reporting pattern

When you finish the audit, report:

- the behavior being audited;
- the code paths and line numbers involved;
- exact issue/PR URLs;
- whether an upstream fix already exists and whether it is merged;
- the likely misclassification risk;
- any protected or user-owned skills that could not be edited.

## Pitfalls

- Do not infer a fix from a search result title alone; confirm against the PR body or source diff.
- Do not use session history as proof of current source state.
- Do not overfit a memory prompt to carry workflow policy.
- Do not treat background-review routing as equivalent to foreground system-prompt routing; check both.
- If a relevant existing skill is user-owned or otherwise protected, leave it untouched and report the limitation explicitly.
