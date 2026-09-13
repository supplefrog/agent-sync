---
name: external-skill-intake
description: Evaluate, install, adapt, or prune skills from external agent-skill ecosystems such as `npx skills`, skills.sh, GitHub skill repos, Claude Code/Cursor/Codex/Antigravity skill folders, or generic `.agents/skills`. Use this before importing non-Hermes skills into Hermes, before deleting old external skill folders, or whenever the user asks whether outside skills are useful. Always inspect source/trust, compare against existing Hermes skills, adapt incompatible assumptions, and verify the final Hermes skill loads.
---

# External Skill Intake

Use this for skill intake into an already selected Hermes host, or ownership-aware cleanup. It does not decide whether Hermes or the existing architecture should be retained.

## First principles

- Do not bulk install skills from a registry or repo.
- Treat install counts and popularity as weak signals only. Inspect the actual `SKILL.md`.
- Prefer official/supported commands over homemade launchers or aliases.
- Keep profile boundaries: install into the active Hermes profile only unless the user explicitly asks to sync profiles.
- For removals, distinguish “unused by Hermes” from “safe to delete.” Archive or ask before destructive cleanup.

## Discovery commands

Check the external CLI and maintenance state when relevant:

```bash
npx --yes skills --help
npm view skills version time.modified repository.url homepage --json
```

Search the broad external catalog:

```bash
npx --yes skills find "browser"
npx --yes skills find "debugging"
npx --yes skills find "dependency upgrade"
npx --yes skills find "api design"
```

List skills in a candidate repo before installing:

```bash
npx --yes skills add owner/repo --list
```

Hermes also has its own skill hub; compare results:

```bash
hermes skills search "query"
hermes skills list
```

## Triage workflow

1. **Identify source and scope**
   - Source repo or local folder.
   - Candidate skill names.
   - Intended agent target (`hermes-agent`, Claude Code, Cursor, Codex, generic `.agents`, etc.).
   - Whether it is already installed under `~/.hermes/skills`, `~/.agents/skills`, or another agent folder.

2. **Inspect before installing**
   - Read `SKILL.md` frontmatter and body.
   - Check supporting files under `references/`, `scripts/`, `templates/`, and `assets/`.
   - Watch for commands that require credentials, services, package installs, or repo-local scripts.

3. **Reject or adapt incompatible assumptions**
   Common incompatibilities:
   - Claude-only frontmatter such as `allowed-tools`.
   - GSD-specific tools or paths such as `gsd_*`, `.gsd/`, or `guided-complete-slice.md`.
   - Repo-local scripts such as `scripts/ci_monitor.cjs` that are not present in the target project.
   - Hardcoded paths inconsistent with the target host's configured discovery roots; `.agents/skills` may be a valid shared source.
   - Instructions that conflict with Hermes tool-use discipline, verification requirements, or the user's provider/tooling preferences.

4. **Compare against existing Hermes skills**
   - Do not reject on category overlap alone.
   - Read the candidate workflow and the overlapping Hermes skill.
   - Keep or patch if the candidate adds a real capability: better steps, script, template, reference, verification, or faster path.
   - Reject as duplicate only when Hermes already does the same workflow and the candidate adds nothing useful.
   - Prefer patching the existing umbrella skill over creating a near-duplicate.

5. **Install narrowly if it is already compatible**

```bash
npx --yes skills add owner/repo --skill skill-name -g -a hermes-agent --copy
```

Use `--copy` when adaptation is likely. Symlinks are acceptable only when upstream updates should remain the single source of truth.

6. **Adapt when needed**
   - Stage a writable copy first.
   - Rewrite instructions as a Hermes skill: tool names, paths, verification steps, and trigger description.
   - Move one-off provenance or long notes into `references/`.
   - Remove unsupported launchers, aliases, and tool assumptions.

7. **Verify**

```bash
hermes skills list
```

Then in-session, verify with `skill_view(name)` or explicitly load it with `/skill <name>` in a fresh Hermes session if needed.

## `.agents/skills` cleanup

`~/.agents/skills` may be shared across agents and configured as a Hermes external skill directory. Inspect `skills.external_dirs` and each host's discovery before assuming the directory is unused.

Before cleanup, check which external agent owns the folder rather than reasoning from Hermes alone:

```bash
# Check whether Hermes skill entries point to an external global skills folder.
# Current Windows Hermes home:
python - <<'PY'
import os, glob
for p in glob.glob(r'{{agent-signal:HERMES_HOME}}/skills/**', recursive=True):
    if os.path.islink(p):
        t=os.path.realpath(p)
        if '.agents' in t.replace('\\', '/'):
            print(p, '->', t)
PY

# If inspecting the retained WSL/GSD environment, check it explicitly and do not assume it is Hermes-owned.
wsl.exe -d openSUSE-Tumbleweed -- bash -lc 'du -sh /root/.agents 2>/dev/null || true; find /root/.agents -maxdepth 2 -type d | sort | sed -n "1,120p"' 2>/dev/null || true
```

If no active agent uses it, prefer a reversible archive first. On this setup, GSD 3.x uses `/root/.agents/skills`; do not archive or delete `/root/.agents` as Hermes clutter unless the user explicitly decides GSD/external agents no longer need it.

Example archive pattern for a confirmed-unused external folder:

```bash
mv /path/to/.agents /path/to/.agents.archive-$(date +%Y%m%d-%H%M%S)
```

Delete only after the user confirms the archive is not needed.

## Decision rule

A candidate is worth adopting when it provides at least one of:

- a workflow Hermes lacks,
- a better checklist for a recurring task,
- a concrete script/template/reference that avoids repeated work,
- or a compatibility lesson worth adding to an existing Hermes skill.

Otherwise, leave it external or remove/archive it. Do not increase the active skill list just because a skill is popular.
