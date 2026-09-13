# External skills intake (`npx skills`, skills.sh, non-Hermes agent skills)

Use this reference when evaluating skills from `npx skills`, skills.sh, GitHub skill repos, or other agent ecosystems before making them part of Hermes.

## What was verified

- `npx skills` resolves to the npm package `skills` from `vercel-labs/skills`.
- It supports Hermes directly with `--agent hermes-agent`.
- Hermes global install target is `~/.hermes/skills/`.
- Generic/global skills may also exist under `~/.agents/skills/`, but Hermes does not automatically load those unless installed/adapted into the Hermes skill tree.
- The CLI can search and list candidate repos:

```bash
npx skills find browser
npx skills find debugging
npx skills add owner/repo --list
```

## Safe intake workflow

1. Load the protected `hermes-agent` skill first for official Hermes skill commands.
2. Search broadly, but do not bulk install:

```bash
npx skills find "dependency upgrade"
npx skills find "api design"
```

3. List a repo before installing anything:

```bash
npx skills add owner/repo --list
```

4. Compare against existing Hermes skills. Do not import duplicates unless the external skill adds a clearly better checklist, reference, or script.
5. Inspect the candidate `SKILL.md` before enabling it. Watch for non-Hermes assumptions:
   - agent-specific tools such as `gsd_*`, Claude-only `allowed-tools`, or repo-local helper scripts that are not present
   - project-local paths such as `.gsd/`, `.claude/`, `.cursor/`, or `scripts/ci_monitor.cjs`
   - commands that require credentials, services, or package installs not stated in the skill
   - instructions that conflict with Hermes tool discipline or user preferences
6. If installing directly, scope narrowly and target Hermes explicitly:

```bash
npx skills add owner/repo --skill skill-name -g -a hermes-agent -y --copy
```

Prefer `--copy` when adaptation is likely; symlinks are better only when you want upstream updates as the single source of truth.

7. If adapting, stage/copy first, rewrite the skill as a class-level Hermes skill, and move session-specific detail into `references/`.
8. Verify after install/adaptation:

```bash
hermes skills list
# then in-session, use skill_view(name) or /skill <name> to confirm it loads
```

## Decision rule

Useful external skills are usually source material, not drop-in truth. Import when they provide a durable workflow/checklist/reference that Hermes lacks. Otherwise, extract the good idea into an existing Hermes umbrella skill or a concise reference file.