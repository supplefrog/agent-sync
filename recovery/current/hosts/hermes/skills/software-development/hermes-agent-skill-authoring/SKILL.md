---
name: hermes-agent-skill-authoring
description: Author or modify skills inside the Hermes Agent source repository for upstream distribution, including repository placement, frontmatter/schema checks, progressive disclosure, tests, and PR verification. Use skill-creator for user-local skills.
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [skills, authoring, hermes-agent, upstream]
    related_skills: [skill-creator, code-change-verification, github-pr-workflow]
---

# Hermes Agent In-Repo Skill Authoring

Use this only for skills that should ship from the Hermes Agent repository. User-local skills belong under the active Hermes home and should be managed with `skill-creator`/`skill_manage` instead.

## 1. Inspect the current repository contract

Run the ownership and overlap decision through `skill-creator` first. This skill owns repository placement and upstream validation, not a second skill-design strategy. If an in-repo candidate overlaps an existing skill, evaluate them under the same fixtures, promote one owner, move unique assets, and remove the loser before publishing.

Do not rely on hardcoded historical paths or size limits. In the active checkout:

- locate the in-repo skills tree and peer categories;
- inspect the current skill loader/validator source;
- read repository contribution guidance;
- inspect two or three related peer skills and existing umbrella owners;
- search for the proposed name/trigger to avoid duplicates.

Use repository-relative paths in plans and changes. The checkout may be on Windows, Linux, WSL, or a worktree.

## 2. Decide whether the change belongs upstream

A distributable skill should provide broadly reusable procedure, integration knowledge, script/template/reference, or a task-class workflow. Do not upstream:

- one user’s stable preferences or environment facts;
- completed-task residue or dated incident logs;
- a generic “be careful/verify/minimize code” prompt;
- a skill that assumes private paths, credentials, or local wrappers;
- a near-duplicate of an existing umbrella.

Generalize local lessons and keep user-specific details in local skills/memory.

## 3. Create the repository artifact

Place the skill under the current repository’s established category/name layout. Use file tools for in-repo creation; do not assume user-home `skill_manage(create)` targets the source checkout.

Frontmatter must match the live validator. At minimum expect a YAML mapping with `name` and `description`, followed by a non-empty body. Quote descriptions containing YAML-sensitive punctuation.

Typical shape:

```yaml
---
name: example-skill
description: Use when <specific trigger>; <distinctive workflow and exclusions>.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [example]
    related_skills: [existing-owner]
---
```

Keep names stable during rewrites. Reference only skills that will resolve for a clean repository install.

## 4. Write for progressive disclosure

The description owns triggering. Include both positive contexts and important exclusions when broad loading would hurt.

Keep `SKILL.md` focused on always-needed decisions and workflow. Put bulky or branch-specific material in:

- `references/` for detailed variants and evidence;
- `scripts/` for deterministic/repeated operations;
- `templates/` for output/config scaffolds;
- `assets/` for non-text support files.

Every line should add procedure, a verified trap, an exact command, or a completion criterion. Remove duplicated rules, motivational rhetoric, stale model/version claims, and no-op advice.

## 5. Validate locally

Use the repository’s own validator/tests when available. At minimum verify:

- frontmatter parses and required fields satisfy current limits;
- directory name/frontmatter name match conventions;
- linked files exist and are referenced correctly;
- no stale/invalid related-skill links;
- example commands use Hermes tools/current CLI syntax;
- scripts have appropriate syntax/tests and no secrets/private paths;
- the final skill loads through the current loader in a fresh/runtime-equivalent check.

For trigger-sensitive or behavior-heavy skills, add realistic positive and near-miss prompts or run a small with/without comparison. Structural validation is enough for obvious documentation/command corrections.

## 6. Review and publish

Use `code-change-verification` for the final diff. Confirm the PR includes only the intended skill/support files and that generated/local artifacts are absent.

Use `github-pr-workflow` for branch, duplicate-PR audit, tests, contribution template, live PR readback, and CI. Report exact validation commands and untested scope.

## Pitfalls

- User-local and in-repo skill trees are different mutation targets.
- A current session may cache its skills index; test through the runtime behavior that matches the current Hermes version.
- Fabricated exact limits are worse than reading the live validator.
- Large skills should become routing indexes with on-demand references, not exceed limits by sediment.
- Upstream skills must work outside the author’s machine and profile.
