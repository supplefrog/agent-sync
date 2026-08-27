# Fleet distribution

## Outcome

Use Agent Signal as the Git-owned source for admitted portable skills while
preserving host-native instructions, adapters, unmanaged skills, and local
changes. The same deterministic snapshot can be checked before it is applied
to any declared machine.

## Ownership

- `registry.json` decides which repository skills are admitted.
- `skills/<name>/` owns admitted portable source.
- `fleet.json` declares machines, participating hosts, and managed skill roots.
- `render/fleet/manifest.json` binds every rendered file and skill hash.
- `<skill-root>/.agent-signal-fleet.json` records only entries applied or adopted
  by this fleet. It never claims ownership of unrelated directories.
- `adapters/` retains intentional Hermes, Codex, and OMP differences. Fleet sync
  does not overwrite host instruction files.

## Commands

```bash
python tools/fleet.py render --machine local-windows
python tools/fleet.py diff --machine local-windows
python tools/fleet.py apply --machine local-windows
python tools/fleet.py verify --machine local-windows
```

`render` is deterministic: the manifest has no clock-dependent fields. `diff`
is read-only. `apply` preflights every declared root before the first mutation.
Within each destination it stages all changed skills, keeps temporary rollback
directories until that destination's state manifest commits, and rolls that
destination back if a mutation or state write fails. Temporary rollback
directories are removed before success returns. `verify` checks rendered bytes,
installed bytes, and managed state.

## Reconciliation rules

| State | Action |
|---|---|
| Desired skill absent | add |
| Existing unmanaged skill exactly matches snapshot | adopt as a rendered copy |
| Existing unmanaged skill differs | conflict; stop before writes |
| Managed skill unchanged and source changed | update |
| Managed skill changed locally | conflict; stop before writes |
| Clean managed skill is no longer admitted | remove |
| Modified managed skill is no longer admitted | conflict; preserve it |
| Unrelated skill | ignore and preserve |

All conflicts are checked before any destination mutation. Resolve a conflict
by either moving the local version back into the source repository and
rerendering, or by explicitly removing/renaming the colliding live directory.
There is intentionally no broad force flag.

## Current scope

The first machine is the Windows command center and uses the standard shared
`~/.agents/skills` root already discovered by Codex and OMP and registered in
Hermes through `skills.external_dirs`. Remote transport is intentionally not
invented before another machine is declared; a later adapter can carry the same
snapshot and manifest over SSH/Tailscale without changing reconciliation.