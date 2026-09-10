---
name: fleet-sync
description: Use when asked to render, diff, sync, propagate, reconcile, or verify admitted agent skills across Hermes, Codex, OMP, or declared machines. Do not use for editing skill content or host-specific instruction adapters.
license: MIT
compatibility: Requires an Agent Sync checkout with fleet.json and Python 3.11+.
metadata:
  author: supplefrog
  version: "1.0.0"
---

# Fleet Sync

Use Agent Sync's deterministic fleet tool. The repository skills and
`registry.json` are authoritative; live host directories are deployments, not
sources.

## Locate the owner

Find the managed skill root containing `.agent-signal-fleet.json`. Its
`source_snapshot` points into the owning Agent Sync checkout. Walk upward from
that snapshot until `fleet.json` is found. If no state exists yet, locate the
checkout containing both `fleet.json` and `tools/fleet.py`. Never guess another
repository or treat a generated snapshot as editable source.

## Procedure

1. Run `python tools/fleet.py render` in the owning checkout.
2. Run `python tools/fleet.py diff` and inspect every proposed action and destination; a scoped repair must not carry unrelated staged changes.
3. For a status or audit request, stop after `diff` and
   `python tools/fleet.py verify`; do not mutate live roots.
4. For an explicit sync, propagation, repair, or apply request, use
   `python tools/reconcile.py plan` followed by `python tools/reconcile.py sync`.
   Follow `cross-agent-surface-engineering` for review and exact additional commit
   paths. This finishes agent updates, local commit, remote push, and verification
   as one job. `fleet.py apply` is a local maintenance primitive, not a completed sync.
5. Confirm fresh discovery from every host declared for the machine. Keep
   host-specific instruction and runtime adapters in their native owners.
6. Report conflicts without forcing through them. Move an intentional local
   change into repository source and rerender, or have the user explicitly
   retire/rename the colliding live directory.

The fleet tool preflights all destinations and attempts rollback within each destination. Destinations commit sequentially: a later failure does not undo earlier commits. Preserve recoverable destination snapshots until post-apply checks pass, and recover earlier destinations after partial failure. Unmanaged collisions and modified managed skills remain conflicts; retired skills are removed only when their bytes match managed state. Do not force collisions or broadly delete skill roots.

Remote transport is allowed only for machines already declared in `fleet.json`.
Adding a machine or transport adapter is a fleet design change, not an ordinary
sync.
