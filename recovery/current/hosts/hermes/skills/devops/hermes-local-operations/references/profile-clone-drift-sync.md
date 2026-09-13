# Hermes profile clone drift sync

Use this when secondary Hermes profiles were cloned from `default` and should differ only in narrow intentional areas such as toolsets, model experiments, descriptions, or isolated state.

## What to inspect

- Config files: `~/.hermes/config.yaml` and `~/.hermes/profiles/<name>/config.yaml`
- Profile metadata: `profile.yaml`
- Prompt/personality baseline: `SOUL.md`
- Skill inventory: `skills/**/SKILL.md`
- Env key names only, not values: `.env`
- Plugin directory presence and names
- Local auth files: `auth.json` presence only unless the task requires auth repair

## Safe sync pattern

1. Load the protected `hermes-agent` skill for official commands.
2. Identify profiles and exclusions first, e.g. keep `oss` separate when it is intentionally experimental.
3. Load YAML with a real parser, not regex edits.
4. Copy only the requested top-level sections from default, preserving intentional toolset/profile differences.
5. Make timestamped backups before each profile write:
   `config.yaml.backup-before-<scope>-sync-YYYYMMDD-HHMMSS`
6. After writing, re-read every changed config and assert exact equality for the synced sections.
7. Run `hermes config check` for default and each changed profile; include excluded profiles if the user asked for a whole-profile inventory.
8. Report both changed profiles and profiles intentionally skipped.

## Drift audit output to give the user

Group differences by practical category rather than dumping raw YAML:

- Main model/provider
- Delegation and auxiliary routing
- CLI toolsets
- Approvals mode
- Display/personality/reasoning/voice settings
- Missing/new config keys after default migrated
- `SOUL.md` hash/size differences
- Skill inventory differences: missing vs extra names
- Plugin/env/auth presence differences

Do not print `.env` values. Active key names are enough for profile drift analysis.

## Common intentional profile boundaries

- `lite`: minimal everyday tools; often no browser/web/vision/delegation.
- `dev`: coding/web/delegation tools; may omit browser/vision.
- `browser-agent`: browser workflow isolation; avoid loading both direct Hermes browser/web and an external browser agent unless intended.
- `oss`: cheap/free experimental route; usually keep model, delegation, aux, and reasoning differences unless explicitly asked to sync them.

## Verification probes

- `hermes profile list`
- `hermes --profile <name> config check`
- YAML equality check for synced sections
- Toolset comparison against intended profile role
- Skill count plus missing/extra skill names, not just totals
